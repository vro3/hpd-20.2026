"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUPS = [REPO_ROOT / "BKUP-021.HS0", REPO_ROOT / "BKUP-058.HS0"]


@pytest.fixture(params=BACKUPS, ids=lambda p: p.name)
def backup_path(request) -> Path:
    """Each test using this fixture runs once per bundled backup file."""
    return request.param
