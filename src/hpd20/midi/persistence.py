"""Persistence for MIDI remap table and recorded patterns.

- Remap lives at ``~/.hpd20-midi-remap.json``
- Recorded patterns are written to ``~/.hpd20-patterns/<timestamp>.json`` on
  demand (one file per recording).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REMAP_PATH = Path.home() / ".hpd20-midi-remap.json"
PATTERNS_DIR = Path.home() / ".hpd20-patterns"


def load_remap() -> dict[int, int]:
    if not REMAP_PATH.exists():
        return {}
    try:
        data = json.loads(REMAP_PATH.read_text())
        return {int(k): int(v) for k, v in data.get("remap", {}).items()}
    except (json.JSONDecodeError, OSError, ValueError) as e:
        log.warning("remap file unreadable: %s", e)
        return {}


def save_remap(remap: dict[int, int]) -> None:
    REMAP_PATH.write_text(
        json.dumps({"remap": {str(k): v for k, v in remap.items()}}, indent=2)
    )


def save_pattern(events: list[dict[str, Any]], name: str | None = None) -> Path:
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{name or 'pattern'}-{ts}.json"
    path = PATTERNS_DIR / filename
    path.write_text(json.dumps({"events": events, "name": name, "recorded_at": ts}, indent=2))
    return path


def list_patterns() -> list[dict[str, Any]]:
    if not PATTERNS_DIR.exists():
        return []
    out = []
    for p in sorted(PATTERNS_DIR.glob("*.json"), reverse=True):
        try:
            d = json.loads(p.read_text())
            out.append({
                "path": str(p),
                "name": d.get("name") or p.stem,
                "recorded_at": d.get("recorded_at"),
                "event_count": len(d.get("events", [])),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return out
