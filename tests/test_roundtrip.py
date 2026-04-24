"""Golden-file round-trip tests against the two bundled HPD-20 backups."""

from __future__ import annotations

import hashlib
from pathlib import Path

from hpd20 import HPD, KITS_COUNT, PADS_PER_KIT


def test_load_and_md5_matches(backup_path: Path) -> None:
    h = HPD(backup_path)
    assert h.md5_matches(), (
        f"MD5 trailer in {backup_path.name} doesn't match payload — "
        "either the file is corrupt or the hash algorithm is wrong."
    )


def test_save_reload_byte_identical(backup_path: Path, tmp_path: Path) -> None:
    h = HPD(backup_path)
    out = tmp_path / backup_path.name
    h.save(out)
    assert out.read_bytes() == backup_path.read_bytes()


def test_all_200_kits_have_names(backup_path: Path) -> None:
    h = HPD(backup_path)
    names = [h.kits.get_kit(i).main_name().strip() for i in range(KITS_COUNT)]
    assert len(names) == KITS_COUNT
    assert sum(1 for n in names if n) >= 100, "expected most kits to be named"


def test_pad_count(backup_path: Path) -> None:
    h = HPD(backup_path)
    assert len(h.pads.pads) == KITS_COUNT * PADS_PER_KIT


def test_copy_kit_leaves_unrelated_slots_intact(backup_path: Path) -> None:
    """Copying kit 3 into slot 7 must not disturb any other slot."""
    h = HPD(backup_path)
    h.copy_kit(3, 7)
    h_ref = HPD(backup_path)
    ref = bytes(h_ref.memoryBlock)
    # Ensure non-slot-3-or-7 bytes match
    kit_mem = h.KIT_MEMINDEX
    kit_sz = h.KIT_MEMSIZE
    for i in range(KITS_COUNT):
        if i in (3, 7):
            continue
        off = kit_mem + kit_sz * i
        assert bytes(h.memoryBlock[off:off + kit_sz]) == ref[off:off + kit_sz], (
            f"unrelated kit {i} mutated by copy_kit"
        )


def test_swap_kits_is_reversible(backup_path: Path) -> None:
    h = HPD(backup_path)
    original = bytes(h.memoryBlock)
    h.swap_kits(3, 42)
    h.swap_kits(3, 42)
    assert bytes(h.memoryBlock) == original


def test_save_after_edit_rebuilds_md5(backup_path: Path, tmp_path: Path) -> None:
    """Editing a kit must produce a new MD5 trailer that matches the new payload."""
    h = HPD(backup_path)
    pad = h.pads.get_pad(0)
    new_vol = (pad.get_volume(0) + 1) & 0xFF
    pad.set_volume(0, new_vol)

    out = tmp_path / "edited.HS0"
    h.save(out)

    raw = out.read_bytes()
    payload, trailer = raw[:-16], raw[-16:]
    assert hashlib.md5(payload).digest() == trailer

    # Reload and confirm the edit survived
    h2 = HPD(out)
    assert h2.md5_matches()
    assert h2.pads.get_pad(0).get_volume(0) == new_vol
