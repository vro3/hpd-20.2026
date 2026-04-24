"""Smoke tests for the FastAPI web UI."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hpd20 import HPD
from hpd20.web import create_app


@pytest.fixture
def client(backup_path: Path) -> TestClient:
    app = create_app(backup_path)
    return TestClient(app)


def test_index_renders(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "HPD-20 Editor" in r.text
    assert "Device view" in r.text
    assert "Grid view" in r.text


def test_kit_page_renders(client: TestClient) -> None:
    r = client.get("/kit/4")
    assert r.status_code == 200
    assert "Kit 5" in r.text


def test_pad_page_renders(client: TestClient) -> None:
    r = client.get("/kit/4/pad/0")
    assert r.status_code == 200
    assert "Layer A" in r.text
    assert "Layer B" in r.text


def test_edit_pad_persists(client: TestClient, backup_path: Path, tmp_path: Path) -> None:
    original_vol = HPD(backup_path).pads.get_pad(0).get_volume(0)
    new_vol = (original_vol + 1) & 0x7F

    # The edit form POSTs form-encoded data; we must supply every field
    r = client.post(
        "/kit/0/pad/0",
        data={
            "volume_a": new_vol,
            "volume_b": 0,
            "pitch_a": 0,
            "pitch_b": 0,
            "pan_a": 0,
            "pan_b": 0,
            "muffling_a": 0,
            "ambient_a": 0,
            "sweep_a": 0,
            "patch_a": 0,
            "patch_b": 0,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303

    # Save to tmp
    out = tmp_path / "edited.HS0"
    r = client.post("/save", data={"dest": str(out)}, follow_redirects=False)
    assert r.status_code == 303
    assert out.exists()

    raw = out.read_bytes()
    assert hashlib.md5(raw[:-16]).digest() == raw[-16:]

    reloaded = HPD(out)
    assert reloaded.pads.get_pad(0).get_volume(0) == new_vol


def test_swap_and_copy_endpoints(client: TestClient) -> None:
    # copy kit 0 to slot 100
    r = client.post("/kit/0/copy/100", follow_redirects=False)
    assert r.status_code == 303

    # swap 0 <-> 150
    r = client.post("/kit/0/swap/150", follow_redirects=False)
    assert r.status_code == 303


def test_bounds_checking(client: TestClient) -> None:
    assert client.get("/kit/200").status_code == 404
    assert client.get("/kit/0/pad/99").status_code == 404
    assert client.post("/kit/999/copy/0").status_code == 404


def test_no_backup_landing_page(tmp_path: Path) -> None:
    """With no backup loaded, index should show the empty state."""
    app = create_app(None)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "No backup loaded" in r.text
