"""Round-trip individual kit export/import."""

from __future__ import annotations

from pathlib import Path

from hpd20 import HPD, PADS_PER_KIT


def test_kit_export_size(backup_path: Path, tmp_path: Path) -> None:
    """Exported kit should be kit header (224) + 17 pads * 68 = 1380 bytes."""
    h = HPD(backup_path)
    out = tmp_path / "kit.bin"
    h.save_kit(5, out)
    assert out.stat().st_size == 224 + PADS_PER_KIT * 68


def test_save_load_kit_roundtrip(backup_path: Path, tmp_path: Path) -> None:
    """Export a kit, load it into a different slot, confirm bytes equal."""
    h = HPD(backup_path)
    kit_file = tmp_path / "kit5.bin"
    h.save_kit(5, kit_file)

    # Capture slot 5 bytes before wiping slot 10
    kit_mem = h.KIT_MEMINDEX
    kit_sz = h.KIT_MEMSIZE
    pad_mem = h.PAD_MEMINDEX
    pad_sz = h.PAD_MEMSIZE
    slot5_kit = bytes(h.memoryBlock[kit_mem + kit_sz * 5 : kit_mem + kit_sz * 6])
    slot5_pads = bytes(
        h.memoryBlock[
            pad_mem + pad_sz * 5 * PADS_PER_KIT : pad_mem + pad_sz * 6 * PADS_PER_KIT
        ]
    )

    h.load_kit(10, kit_file)

    slot10_kit = bytes(h.memoryBlock[kit_mem + kit_sz * 10 : kit_mem + kit_sz * 11])
    slot10_pads = bytes(
        h.memoryBlock[
            pad_mem + pad_sz * 10 * PADS_PER_KIT : pad_mem + pad_sz * 11 * PADS_PER_KIT
        ]
    )
    assert slot10_kit == slot5_kit
    assert slot10_pads == slot5_pads


def test_save_all_kits_produces_files(backup_path: Path, tmp_path: Path) -> None:
    """``save_all_kits`` writes one file per unique (sanitized) kit name.

    HPD-20 factory presets have many duplicate names across slots, so the
    200 kits collapse to ~100-110 unique files. Verify the process works
    and the files have the expected size (224 kit header + 17 * 68 pads).
    """
    h = HPD(backup_path)
    h.save_all_kits(tmp_path)
    files = list(tmp_path.glob("*.kit"))
    assert files, "save_all_kits produced no files"
    for f in files:
        assert f.stat().st_size == 224 + PADS_PER_KIT * 68, f"{f.name} wrong size"
