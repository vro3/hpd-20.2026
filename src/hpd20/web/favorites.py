"""Persistent favorite-instrument storage.

A single JSON file at ``~/.hpd20-favorites.json``:

    {"ids": [74, 198, 351, ...]}

Order preserves the order the user starred them. Single-user tool, no
locking; writes are small (a few hundred bytes at most).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

FAVORITES_PATH = Path.home() / ".hpd20-favorites.json"


def load() -> list[int]:
    if not FAVORITES_PATH.exists():
        return []
    try:
        data = json.loads(FAVORITES_PATH.read_text())
        ids = data.get("ids", [])
        return [int(i) for i in ids if isinstance(i, int) or str(i).isdigit()]
    except (json.JSONDecodeError, OSError) as e:
        log.warning("favorites file unreadable (%s): %s", FAVORITES_PATH, e)
        return []


def save(ids: list[int]) -> None:
    FAVORITES_PATH.write_text(json.dumps({"ids": ids}, indent=2))


def toggle(instrument_id: int) -> list[int]:
    ids = load()
    if instrument_id in ids:
        ids.remove(instrument_id)
    else:
        ids.append(instrument_id)
    save(ids)
    return ids
