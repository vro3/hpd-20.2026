"""SVG geometry for the HPD-20 pad skin.

Layout derived from the device's own manual — a circular playing surface
with four large quadrant pads (M1-M4) around a small centre pad (M5),
ringed across the upper half by eight narrow wedge pads (S1-S8).
D-Beam, Head, Rim, HH are auxiliary triggers shown as rectangles above.

Pad slot index (matches the HPD-20 memory layout):
    0..4   M1, M2, M3, M4, M5
    5..12  S1, S2, S3, S4, S5, S6, S7, S8
    13..16 D-Beam, Head, Rim, HH
"""

from __future__ import annotations

import math
from typing import Any

# Canvas — tall enough to fit a control-panel strip above the disc.
VIEW_W = 1000
VIEW_H = 950

# Disc centre and radii.
CX, CY = 500, 555
R_BEZEL_OUTER = 430
R_BEZEL_INNER = 415
R_S_OUTER = 410
R_S_INNER = 315
R_M_OUTER = 305
R_M5_VISIBLE = 58     # the centre pad we draw
R_M_INNER = 64        # how far the M-quadrant "hole" reaches (tiny gap round M5)


def _polar(cx: float, cy: float, r: float, angle_deg: float) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def annular_wedge(
    cx: float, cy: float,
    r_inner: float, r_outer: float,
    a1_deg: float, a2_deg: float,
) -> str:
    x1i, y1i = _polar(cx, cy, r_inner, a1_deg)
    x1o, y1o = _polar(cx, cy, r_outer, a1_deg)
    x2i, y2i = _polar(cx, cy, r_inner, a2_deg)
    x2o, y2o = _polar(cx, cy, r_outer, a2_deg)
    large = 1 if (a2_deg - a1_deg) > 180 else 0
    return (
        f"M {x1i:.2f} {y1i:.2f} "
        f"L {x1o:.2f} {y1o:.2f} "
        f"A {r_outer:.2f} {r_outer:.2f} 0 {large} 1 {x2o:.2f} {y2o:.2f} "
        f"L {x2i:.2f} {y2i:.2f} "
        f"A {r_inner:.2f} {r_inner:.2f} 0 {large} 0 {x1i:.2f} {y1i:.2f} Z"
    )


def centroid(
    cx: float, cy: float,
    r_inner: float, r_outer: float,
    a1_deg: float, a2_deg: float,
) -> tuple[float, float]:
    mid_angle = (a1_deg + a2_deg) / 2
    mid_r = (r_inner + r_outer) / 2
    return _polar(cx, cy, mid_r, mid_angle)


# M1 is bottom-left (6 o'clock -> 9 o'clock), going clockwise in SVG angle terms.
# In SVG, angle 0 = east (3 o'clock), sin(+) points down, so 90° = south (6 o'clock),
# 180° = west (9 o'clock), 270° = north (12 o'clock).
M_QUADRANTS = [
    ("M1", 90.0, 180.0),
    ("M2", 0.0, 90.0),
    ("M3", 180.0, 270.0),
    ("M4", 270.0, 360.0),
]

# The 8 S pads divide the TOP semicircle (180° -> 360°) into equal wedges.
S_WEDGE_DEG = 180.0 / 8


def _s_wedge(index: int) -> tuple[float, float]:
    a1 = 180.0 + index * S_WEDGE_DEG
    a2 = 180.0 + (index + 1) * S_WEDGE_DEG
    return a1, a2


# External/auxiliary triggers rendered as rectangles in the header strip.
# (x, y, w, h, label_anchor_x, label_anchor_y)
AUX_RECTS = [
    ("D-Beam", 400, 25, 200, 40),
    ("HH",     30,  25, 100, 40),
    ("Head",   140, 25, 100, 40),
    ("Rim",    250, 25, 100, 40),
]


def _button_shape(cx: float, cy: float, r: float) -> str:
    """Return the triangle-play icon points, scaled for a given button radius."""
    return (
        f"{cx - r * 0.33:.1f},{cy - r * 0.44:.1f} "
        f"{cx - r * 0.33:.1f},{cy + r * 0.44:.1f} "
        f"{cx + r * 0.44:.1f},{cy:.1f}"
    )


# Pads that need a smaller play button because their wedge sits right at
# 12 o'clock where the bezel is tightest.
_SMALL_BUTTON_SLOTS = {8, 9}  # S4, S5
DEFAULT_BUTTON_RADIUS = 18
SMALL_BUTTON_RADIUS = 13


def build_pad_geometries() -> list[dict[str, Any]]:
    """Return one geometry dict per pad slot (0..16), with drawing data."""
    geoms: list[dict[str, Any]] = []

    # Slots 0..3 - the four M quadrants. Play button sits centred under
    # the label stack (name + instrument + note + volume), outside the
    # text block so it doesn't overlap any label.
    for idx, (name, a1, a2) in enumerate(M_QUADRANTS):
        cx_label, cy_label = centroid(CX, CY, R_M_INNER, R_M_OUTER, a1, a2)
        geoms.append({
            "slot": idx,
            "name": name,
            "shape": "wedge",
            "path": annular_wedge(CX, CY, R_M_INNER, R_M_OUTER, a1, a2),
            "label_x": cx_label,
            "label_y": cy_label,
            "play_x": cx_label,
            "play_y": cy_label + 54,
            "family": "main",
        })

    # Slot 4 - M5 centre circle (smaller, so play button sits just below the
    # label stack but inside the circle).
    geoms.append({
        "slot": 4,
        "name": "M5",
        "shape": "circle",
        "cx": CX,
        "cy": CY,
        "r": R_M5_VISIBLE,
        "label_x": CX,
        "label_y": CY,
        "play_x": CX,
        "play_y": CY + 32,
        "family": "main",
    })

    # Slots 5..12 - the eight S wedges across the top
    for i in range(8):
        a1, a2 = _s_wedge(i)
        cx_label, cy_label = centroid(CX, CY, R_S_INNER, R_S_OUTER, a1, a2)
        geoms.append({
            "slot": 5 + i,
            "name": f"S{i + 1}",
            "shape": "wedge",
            "path": annular_wedge(CX, CY, R_S_INNER, R_S_OUTER, a1, a2),
            "label_x": cx_label,
            "label_y": cy_label,
            "play_x": cx_label,
            "play_y": cy_label + 32,
            "family": "side",
        })

    # Slots 13..16 - auxiliary trigger rects at the top of the SVG.
    # Aux rects are short (40px tall), so the play button lives on the right
    # side *inside* the rect — putting it below would overlap the brand strip.
    # Labels shift left to make room.
    order = [("D-Beam", 13), ("Head", 14), ("Rim", 15), ("HH", 16)]
    for aux_name, slot in order:
        rect = next(r for r in AUX_RECTS if r[0] == aux_name)
        _, x, y, w, h = rect
        geoms.append({
            "slot": slot,
            "name": aux_name,
            "shape": "rect",
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "label_x": x + (w - 24) / 2,   # centre of the area left of the button
            "label_y": y + h / 2 + 4,
            "play_x": x + w - 20,          # right side of rect, 20px from edge
            "play_y": y + h / 2,
            "family": "aux",
        })

    # Per-pad play-button radius + triangle points (computed here so the
    # template just renders what it's told).
    for g in geoms:
        r = SMALL_BUTTON_RADIUS if g["slot"] in _SMALL_BUTTON_SLOTS else DEFAULT_BUTTON_RADIUS
        g["play_r"] = r
        g["play_triangle"] = _button_shape(g["play_x"], g["play_y"], r)

    return geoms


# Build once at import time — geometry is static.
PAD_GEOMETRIES: list[dict[str, Any]] = build_pad_geometries()
