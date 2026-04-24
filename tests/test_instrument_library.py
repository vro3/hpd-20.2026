"""Instrument library — search, favorites, apply-to-pad."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hpd20.web import create_app, favorites


@pytest.fixture
def client(backup_path: Path) -> TestClient:
    app = create_app(backup_path)
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolated_favorites(tmp_path, monkeypatch):
    """Redirect the favorites file into a tmp dir so tests don't clobber real data."""
    fake = tmp_path / "fav.json"
    monkeypatch.setattr(favorites, "FAVORITES_PATH", fake)
    yield


def test_api_instruments_returns_full_list(client: TestClient) -> None:
    r = client.get("/api/instruments")
    assert r.status_code == 200
    data = r.json()
    # there are ~850 instruments; just check it's a large-ish list
    assert len(data["items"]) > 500
    first = data["items"][0]
    assert "id" in first and "name" in first and "favorite" in first


def test_api_instruments_filters_by_query(client: TestClient) -> None:
    r = client.get("/api/instruments?q=conga")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert "conga" in item["name"].lower()


def test_toggle_favorite_roundtrip(client: TestClient) -> None:
    # star instrument id 74
    r = client.post("/api/favorites/74")
    assert r.status_code == 200
    assert 74 in r.json()["favorites"]

    # it shows up in /api/instruments as favorite=True
    r = client.get("/api/instruments?q=")
    ids_favored = [i["id"] for i in r.json()["items"] if i["favorite"]]
    assert 74 in ids_favored

    # unstarring removes it
    r = client.post("/api/favorites/74")
    assert 74 not in r.json()["favorites"]


def test_apply_patch_endpoint(client: TestClient, backup_path: Path) -> None:
    # Apply instrument 100 to kit 0 pad 0 layer A via HTMX
    r = client.post(
        "/kit/0/pad/0/patch",
        headers={"HX-Request": "true"},
        data={"layer": 0, "instrument_id": 100},
    )
    assert r.status_code == 200
    assert "pad-editor-inner" in r.text
    # Sanity: the response fragment should reference the new patch id
    assert "100" in r.text


def test_favorites_persist_to_disk(tmp_path, monkeypatch) -> None:
    fake = tmp_path / "fav.json"
    monkeypatch.setattr(favorites, "FAVORITES_PATH", fake)
    favorites.toggle(10)
    favorites.toggle(20)
    data = json.loads(fake.read_text())
    assert data["ids"] == [10, 20]
    # toggle a second time removes
    favorites.toggle(10)
    data = json.loads(fake.read_text())
    assert data["ids"] == [20]
