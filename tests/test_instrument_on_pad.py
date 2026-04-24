"""Rendered skin shows instrument name per pad, truncated per family."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hpd20.web import create_app
from hpd20.web.app import _truncate


@pytest.fixture
def client(backup_path: Path) -> TestClient:
    app = create_app(backup_path)
    return TestClient(app)


class TestTruncate:
    def test_short_name_unchanged(self):
        assert _truncate("Conga", 14) == "Conga"

    def test_exact_length_unchanged(self):
        assert _truncate("exactly14chars", 14) == "exactly14chars"

    def test_over_length_ellipsis(self):
        assert _truncate("A very long instrument name", 14) == "A very long i…"
        assert len(_truncate("A very long instrument name", 14)) == 14


def test_skin_renders_instrument_name_on_pads(client: TestClient) -> None:
    r = client.get("/kit/4")  # TwentyFunky — M1 is "TR-707 Snare"
    assert r.status_code == 200
    # Big-pad text elements exist with the class and the truncated name appears.
    assert 'class="pad-instr"' in r.text
    assert "TR-707 Snare" in r.text  # fits in 14 chars, so no truncation on M1


def test_kit_change_updates_pad_instrument(client: TestClient) -> None:
    r5 = client.get("/kit/4")   # TwentyFunky
    r12 = client.get("/kit/11")  # FatStep
    assert r5.status_code == 200 and r12.status_code == 200
    # The instrument text on M1 differs between kits (not a stale label)
    import re
    def extract_m1_instr(html: str) -> str:
        # Find the first occurrence of pad-instr text in the HTML
        m = re.search(r'class="pad-instr"[^>]*>([^<]+)<', html)
        return m.group(1) if m else ""
    assert extract_m1_instr(r5.text) != extract_m1_instr(r12.text)
