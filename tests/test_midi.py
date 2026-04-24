"""MIDI engine + API — tested with a fake mido backend (no hardware needed)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from hpd20.midi import MidiEngine
from hpd20.midi import persistence as midi_persistence
from hpd20.web import create_app


class FakePort:
    """Stand-in for mido input/output ports."""

    def __init__(self, name: str):
        self.name = name
        self.closed = False
        self.sent: list = []
        self._callback = None

    def send(self, msg):
        self.sent.append(msg)

    def close(self):
        self.closed = True


class FakeMessage:
    def __init__(self, type: str, **kw):
        self.type = type
        self.note = kw.get("note")
        self.velocity = kw.get("velocity")
        self.channel = kw.get("channel", 0)
        self.program = kw.get("program")
        self.control = kw.get("control")
        self.value = kw.get("value")

    def copy(self, **kw):
        m = FakeMessage(self.type,
                        note=self.note, velocity=self.velocity,
                        channel=self.channel, program=self.program,
                        control=self.control, value=self.value)
        for k, v in kw.items():
            setattr(m, k, v)
        return m


@pytest.fixture
def fake_mido(monkeypatch):
    """Swap out the real mido module attached to MidiEngine with a fake."""
    import hpd20.midi.engine as engine_mod

    fake = MagicMock()
    fake.get_input_names = MagicMock(return_value=["Fake Input A", "Fake Input B"])
    fake.get_output_names = MagicMock(return_value=["Fake HPD-20"])

    def make_input(name, callback=None):
        port = FakePort(name)
        port._callback = callback
        return port
    fake.open_input = MagicMock(side_effect=make_input)

    def make_output(name):
        return FakePort(name)
    fake.open_output = MagicMock(side_effect=make_output)
    fake.Message = FakeMessage

    monkeypatch.setattr(engine_mod, "mido", fake)
    return fake


@pytest.fixture(autouse=True)
def isolate_midi_persistence(tmp_path, monkeypatch):
    """Redirect remap + patterns onto a tmp dir."""
    monkeypatch.setattr(midi_persistence, "REMAP_PATH", tmp_path / "remap.json")
    monkeypatch.setattr(midi_persistence, "PATTERNS_DIR", tmp_path / "patterns")


class TestMidiEngine:
    def test_list_devices(self, fake_mido):
        engine = MidiEngine()
        d = engine.list_devices()
        assert d["inputs"] == ["Fake Input A", "Fake Input B"]
        assert d["outputs"] == ["Fake HPD-20"]

    def test_connect_opens_ports(self, fake_mido):
        engine = MidiEngine()
        engine.connect("Fake Input A", "Fake HPD-20")
        fake_mido.open_input.assert_called_once()
        fake_mido.open_output.assert_called_once()
        s = engine.status()
        assert s["input"] == "Fake Input A"
        assert s["output"] == "Fake HPD-20"

    def test_disconnect_closes_ports(self, fake_mido):
        engine = MidiEngine()
        engine.connect("Fake Input A", "Fake HPD-20")
        engine.close()
        s = engine.status()
        assert s["input"] is None
        assert s["output"] is None

    def test_note_forwards_through_engine(self, fake_mido):
        engine = MidiEngine()
        engine.connect("Fake Input A", "Fake HPD-20")
        in_port = engine._in_port
        out_port = engine._out_port

        # Simulate incoming note
        msg = FakeMessage("note_on", note=60, velocity=100)
        in_port._callback(msg)

        # It was forwarded to the output
        assert len(out_port.sent) == 1
        assert out_port.sent[0].note == 60

    def test_remap_rewrites_note_before_forwarding(self, fake_mido):
        engine = MidiEngine()
        engine.connect("Fake Input A", "Fake HPD-20")
        engine.set_remap(60, 36)
        engine._in_port._callback(FakeMessage("note_on", note=60, velocity=100))
        # The forwarded note is the remapped one
        assert engine._out_port.sent[0].note == 36

    def test_recorder_captures_events(self, fake_mido):
        engine = MidiEngine()
        engine.connect("Fake Input A", "Fake HPD-20")
        engine.start_recording()
        engine._in_port._callback(FakeMessage("note_on", note=60, velocity=100))
        engine._in_port._callback(FakeMessage("note_off", note=60, velocity=0))
        events = engine.stop_recording()
        assert len(events) == 2
        assert events[0]["type"] == "note_on"
        assert events[0]["note"] == 60
        assert events[1]["type"] == "note_off"

    def test_program_change_sent(self, fake_mido):
        engine = MidiEngine()
        engine.connect(None, "Fake HPD-20")
        engine.send_program_change(42)
        msgs = engine._out_port.sent
        assert len(msgs) == 1
        assert msgs[0].type == "program_change"
        assert msgs[0].program == 42

    def test_switch_kit_over_128_sends_bank_select(self, fake_mido):
        engine = MidiEngine()
        engine.connect(None, "Fake HPD-20")
        engine.switch_kit(150)
        msgs = engine._out_port.sent
        # CC 0, CC 32, Program Change
        assert msgs[0].type == "control_change" and msgs[0].control == 0
        assert msgs[1].type == "control_change" and msgs[1].control == 32
        assert msgs[2].type == "program_change" and msgs[2].program == 22  # 150 - 128

    def test_subscribers_receive_events(self, fake_mido):
        engine = MidiEngine()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        engine.bind_loop(loop)

        q = engine.subscribe()
        engine.connect("Fake Input A", None)  # publishes a "status" event first
        engine._in_port._callback(FakeMessage("note_on", note=72, velocity=90))
        loop.run_until_complete(asyncio.sleep(0.05))

        # Drain until we find the note_on (status events come first)
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        note_events = [e for e in events if e["type"] == "note_on"]
        assert len(note_events) == 1
        assert note_events[0]["note"] == 72
        loop.close()


@pytest.fixture
def client(backup_path: Path, fake_mido) -> TestClient:
    app = create_app(backup_path)
    return TestClient(app)


class TestMidiRoutes:
    def test_devices_endpoint(self, client):
        r = client.get("/api/midi/devices")
        assert r.status_code == 200
        assert "inputs" in r.json()

    def test_connect_and_status(self, client):
        r = client.post(
            "/api/midi/connect",
            data={"input_name": "Fake Input A", "output_name": "Fake HPD-20"},
        )
        assert r.status_code == 200
        s = client.get("/api/midi/status").json()
        assert s["input"] == "Fake Input A"
        assert s["output"] == "Fake HPD-20"

    def test_remap_crud(self, client):
        r = client.post("/api/midi/remap", data={"src": 60, "dst": 36})
        assert r.status_code == 200
        assert r.json()["remap"]["60"] == 36
        r = client.delete("/api/midi/remap/60")
        assert "60" not in r.json()["remap"]

    def test_kit_change_requires_open_output(self, client):
        # Can't send kit change without an output port
        r = client.post("/api/midi/kit-change/5")
        assert r.status_code == 400

    def test_kit_change_sends_when_connected(self, client):
        client.post("/api/midi/connect", data={"output_name": "Fake HPD-20"})
        r = client.post("/api/midi/kit-change/5")
        assert r.status_code == 200
        assert r.json()["kit"] == 5

    def test_pad_lookup_returns_note_to_slot(self, client):
        r = client.get("/api/midi/pad-lookup/4")
        assert r.status_code == 200
        data = r.json()
        assert data["kit"] == 4
        assert isinstance(data["note_to_slot"], dict)

    def test_record_start_stop(self, client):
        client.post("/api/midi/connect", data={"input_name": "Fake Input A"})
        client.post("/api/midi/record/start")
        # Wait for recording to be flagged
        s = client.get("/api/midi/status").json()
        assert s["recording"] is True
        r = client.post("/api/midi/record/stop", data={"name": "test"})
        body = r.json()
        assert body["ok"] is True
        assert body["recording"] is False
