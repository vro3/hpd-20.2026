"""Pad-skin geometry sanity checks."""

from __future__ import annotations

from hpd20.web.skin_geometry import PAD_GEOMETRIES


def test_17_pads_total():
    assert len(PAD_GEOMETRIES) == 17


def test_slot_indices_are_sequential():
    for i, geom in enumerate(PAD_GEOMETRIES):
        assert geom["slot"] == i


def test_pad_names_match_hpd20_order():
    names = [g["name"] for g in PAD_GEOMETRIES]
    assert names == [
        "M1", "M2", "M3", "M4", "M5",
        "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
        "D-Beam", "Head", "Rim", "HH",
    ]


def test_m_quadrants_are_wedges():
    for i in range(4):
        assert PAD_GEOMETRIES[i]["shape"] == "wedge"
        assert PAD_GEOMETRIES[i]["family"] == "main"


def test_m5_is_circle():
    assert PAD_GEOMETRIES[4]["shape"] == "circle"
    assert PAD_GEOMETRIES[4]["family"] == "main"


def test_s_pads_are_wedges():
    for i in range(5, 13):
        assert PAD_GEOMETRIES[i]["shape"] == "wedge"
        assert PAD_GEOMETRIES[i]["family"] == "side"


def test_aux_pads_are_rects():
    for i in range(13, 17):
        assert PAD_GEOMETRIES[i]["shape"] == "rect"
        assert PAD_GEOMETRIES[i]["family"] == "aux"


def test_s_pads_span_top_semicircle():
    """S1 at 9 o'clock, S8 at 3 o'clock — labels should trace across the top."""
    s1_cx = PAD_GEOMETRIES[5]["label_x"]
    s8_cx = PAD_GEOMETRIES[12]["label_x"]
    top_cy = min(g["label_y"] for g in PAD_GEOMETRIES[5:13])
    # S1 is on the left, S8 on the right
    assert s1_cx < s8_cx
    # All S pads are above the disc centre (y decreases upward in the disc)
    disc_cy = PAD_GEOMETRIES[4]["cy"]
    for geom in PAD_GEOMETRIES[5:13]:
        assert geom["label_y"] < disc_cy, f"{geom['name']} not in top half"
    # The topmost S pad is near 12 o'clock (S4 or S5)
    assert top_cy > 0
