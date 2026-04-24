"""Pad-swap within a kit (e.g. M1 <-> M2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hpd20 import HPD
from hpd20.web import create_app


@pytest.fixture
def client(backup_path: Path) -> TestClient:
    app = create_app(backup_path)
    return TestClient(app)


def test_swap_pads_in_kit_core(backup_path: Path) -> None:
    """Directly exercise HPD.swap_pads_in_kit and verify reversibility."""
    h = HPD(backup_path)
    kit = 5
    a, b = 0, 1  # M1 <-> M2

    # Capture bytes before
    pm, ps = h.PAD_MEMINDEX, h.PAD_MEMSIZE
    before_a = bytes(h.memoryBlock[pm + ps * (kit * h.PADS_PER_KIT + a): pm + ps * (kit * h.PADS_PER_KIT + a + 1)])
    before_b = bytes(h.memoryBlock[pm + ps * (kit * h.PADS_PER_KIT + b): pm + ps * (kit * h.PADS_PER_KIT + b + 1)])

    h.swap_pads_in_kit(kit, a, b)

    after_a = bytes(h.memoryBlock[pm + ps * (kit * h.PADS_PER_KIT + a): pm + ps * (kit * h.PADS_PER_KIT + a + 1)])
    after_b = bytes(h.memoryBlock[pm + ps * (kit * h.PADS_PER_KIT + b): pm + ps * (kit * h.PADS_PER_KIT + b + 1)])

    assert after_a == before_b
    assert after_b == before_a

    # swapping again restores the original
    h.swap_pads_in_kit(kit, a, b)
    final_a = bytes(h.memoryBlock[pm + ps * (kit * h.PADS_PER_KIT + a): pm + ps * (kit * h.PADS_PER_KIT + a + 1)])
    assert final_a == before_a


def test_swap_same_slot_is_noop(backup_path: Path) -> None:
    h = HPD(backup_path)
    original = bytes(h.memoryBlock)
    h.swap_pads_in_kit(5, 3, 3)
    assert bytes(h.memoryBlock) == original


def test_swap_endpoint(client: TestClient) -> None:
    r = client.post("/kit/5/pad-swap/0/1", follow_redirects=False)
    assert r.status_code == 303


def test_swap_endpoint_bounds(client: TestClient) -> None:
    assert client.post("/kit/5/pad-swap/99/0").status_code == 404
    assert client.post("/kit/999/pad-swap/0/1").status_code == 404
