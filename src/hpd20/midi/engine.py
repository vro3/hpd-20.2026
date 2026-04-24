"""MIDI engine: ports, remap, recorder, event bus.

The engine owns one input port and one output port (either can be ``None``).
Messages arriving on the input run through :py:meth:`_on_message` in
``python-rtmidi``'s callback thread; we apply the note remap, forward to the
output, optionally record, and publish an event to every async subscriber.

SSE subscribers are :py:class:`asyncio.Queue` instances. Because the rtmidi
thread and the asyncio loop are different contexts, publishes hop the loop
via :py:meth:`asyncio.AbstractEventLoop.call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

log = logging.getLogger(__name__)


class MidiUnavailable(RuntimeError):
    """Raised when the ``midi`` extra isn't installed."""


try:
    import mido
except ImportError:  # pragma: no cover
    mido = None  # type: ignore


@dataclass
class MidiEvent:
    """One event published onto the bus."""

    type: str                     # "note_on", "note_off", "program_change", "status"
    ts: float                     # epoch seconds
    note: int | None = None       # remapped note (what was forwarded)
    original_note: int | None = None  # raw incoming note
    velocity: int | None = None
    program: int | None = None
    channel: int | None = None
    message: str | None = None    # for "status" events

    def as_json(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class MidiEngine:
    def __init__(self) -> None:
        if mido is None:
            raise MidiUnavailable(
                "mido not installed — run: pip install 'hpd20[midi]'"
            )
        self._in_port: Any = None
        self._out_port: Any = None
        self._in_name: str | None = None
        self._out_name: str | None = None
        self.remap: dict[int, int] = {}        # {from_note: to_note}
        self._recording: list[tuple[float, Any]] | None = None
        self._record_start_ts: float = 0.0
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    # ---------- lifecycle ----------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def close(self) -> None:
        with self._lock:
            for port in (self._in_port, self._out_port):
                if port:
                    with contextlib.suppress(Exception):
                        port.close()
            self._in_port = self._out_port = None
            self._in_name = self._out_name = None

    # ---------- device listing / connection ----------

    def list_devices(self) -> dict[str, list[str]]:
        return {
            "inputs": mido.get_input_names(),
            "outputs": mido.get_output_names(),
        }

    def status(self) -> dict[str, Any]:
        return {
            "input": self._in_name,
            "output": self._out_name,
            "recording": self._recording is not None,
            "recording_event_count": len(self._recording) if self._recording else 0,
            "remap": {str(k): v for k, v in self.remap.items()},
        }

    def connect(self, input_name: str | None, output_name: str | None) -> None:
        """(Re-)open ports. Passing ``None`` for a side closes that direction."""
        with self._lock:
            if self._in_port:
                self._in_port.close()
                self._in_port = None
            if self._out_port:
                self._out_port.close()
                self._out_port = None

            if input_name:
                self._in_port = mido.open_input(input_name, callback=self._on_message)
                self._in_name = input_name
            else:
                self._in_name = None

            if output_name:
                self._out_port = mido.open_output(output_name)
                self._out_name = output_name
            else:
                self._out_name = None

        self._publish(MidiEvent(type="status", ts=time.time(),
                                message=f"connected in={input_name} out={output_name}"))

    # ---------- remap ----------

    def set_remap(self, src: int, dst: int) -> None:
        with self._lock:
            self.remap[src] = dst

    def clear_remap(self, src: int | None = None) -> None:
        with self._lock:
            if src is None:
                self.remap.clear()
            else:
                self.remap.pop(src, None)

    # ---------- program change ----------

    def send_program_change(self, program: int, channel: int = 0) -> None:
        """Send a Program Change to the HPD-20 (switches kit)."""
        if self._out_port is None:
            raise RuntimeError("No MIDI output port open")
        self._out_port.send(mido.Message("program_change", program=program & 0x7F,
                                         channel=channel))

    def send_bank_select(self, bank: int, channel: int = 0) -> None:
        """Bank-select pair (CC 0 + CC 32) for reaching kits beyond 128."""
        if self._out_port is None:
            raise RuntimeError("No MIDI output port open")
        self._out_port.send(mido.Message("control_change", control=0,
                                         value=(bank >> 7) & 0x7F, channel=channel))
        self._out_port.send(mido.Message("control_change", control=32,
                                         value=bank & 0x7F, channel=channel))

    def switch_kit(self, kit_index: int, channel: int = 0) -> None:
        """Send a kit change via Program Change (and Bank Select for > 127)."""
        if kit_index >= 128:
            self.send_bank_select(1, channel)  # bank 1 = kits 128..255
        else:
            self.send_bank_select(0, channel)
        self.send_program_change(kit_index % 128, channel)

    # ---------- recorder ----------

    def start_recording(self) -> None:
        with self._lock:
            self._recording = []
            self._record_start_ts = time.time()

    def stop_recording(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._recording is None:
                return []
            events = [
                {"t": t - self._record_start_ts, **self._msg_to_dict(msg)}
                for (t, msg) in self._recording
            ]
            self._recording = None
            return events

    # ---------- event subscription ----------

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    # ---------- internals ----------

    def _on_message(self, msg: Any) -> None:
        """Runs on the rtmidi callback thread."""
        try:
            forwarded = msg
            original_note: int | None = None
            if msg.type in ("note_on", "note_off"):
                original_note = msg.note
                remapped = self.remap.get(msg.note)
                if remapped is not None and remapped != msg.note:
                    forwarded = msg.copy(note=remapped)
            if self._out_port is not None:
                self._out_port.send(forwarded)
            if self._recording is not None:
                self._recording.append((time.time(), forwarded))
            self._publish(MidiEvent(
                type=forwarded.type,
                ts=time.time(),
                note=getattr(forwarded, "note", None),
                original_note=original_note,
                velocity=getattr(forwarded, "velocity", None),
                program=getattr(forwarded, "program", None),
                channel=getattr(forwarded, "channel", None),
            ))
        except Exception as e:  # pragma: no cover
            log.exception("midi callback error: %s", e)

    def _publish(self, event: MidiEvent) -> None:
        payload = event.as_json()
        if self._loop is None:
            return
        with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            self._loop.call_soon_threadsafe(self._try_put, q, payload)

    @staticmethod
    def _try_put(q: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
        # Drop events if a slow client's queue is full rather than blocking the
        # rtmidi callback thread.
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(event)

    @staticmethod
    def _msg_to_dict(msg: Any) -> dict[str, Any]:
        return {
            "type": msg.type,
            "note": getattr(msg, "note", None),
            "velocity": getattr(msg, "velocity", None),
            "channel": getattr(msg, "channel", None),
            "program": getattr(msg, "program", None),
        }
