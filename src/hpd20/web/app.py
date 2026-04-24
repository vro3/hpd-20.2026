"""FastAPI app for editing an HPD-20 memory dump."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..core import HPD, PAD_NAMES, PADS_PER_KIT, get_note_name
from ..instrumentname import (
    get_complete_instrument_list,
    get_instrument_name,
    get_instrument_pitch,
)
from ..instrumentname import (
    instruments as INSTRUMENT_TABLE,
)
from . import favorites
from .skin_geometry import PAD_GEOMETRIES, VIEW_H, VIEW_W

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


class AppState:
    """Holds the single loaded backup and its source path."""

    def __init__(self) -> None:
        self.backup: HPD | None = None
        self.backup_path: Path | None = None
        self.dirty: bool = False

    def require(self) -> HPD:
        if self.backup is None:
            raise HTTPException(400, "No backup loaded. Pass a path to hpd20-web.")
        return self.backup

    def load(self, path: Path) -> None:
        self.backup = HPD(path)
        self.backup_path = path
        self.dirty = False

    def mark_dirty(self) -> None:
        self.dirty = True


def create_app(initial_backup: Path | None = None) -> FastAPI:
    app = FastAPI(title="HPD-20 Editor", version="0.1.0")
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    state = AppState()
    if initial_backup is not None:
        state.load(Path(initial_backup))

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, kit: int = 0):
        if state.backup is None:
            return templates.TemplateResponse(
                request, "no_backup.html", {"cwd": Path.cwd()}
            )
        return _render_kit(request, templates, state, kit)

    @app.get("/kit/{kit_index}", response_class=HTMLResponse)
    def view_kit(request: Request, kit_index: int):
        _bounds_check_kit(kit_index)
        return _render_kit(request, templates, state, kit_index)

    @app.get("/kit/{kit_index}/pad/{pad_slot}", response_class=HTMLResponse)
    def view_pad(request: Request, kit_index: int, pad_slot: int):
        _bounds_check_kit(kit_index)
        _bounds_check_pad(pad_slot)
        # HTMX asks for just the form fragment; full page requests get the
        # whole kit page with this pad pre-selected on the right.
        if request.headers.get("HX-Request"):
            return _render_pad_fragment(request, templates, state, kit_index, pad_slot)
        return _render_kit(request, templates, state, kit_index, selected_pad=pad_slot)

    @app.post("/kit/{kit_index}/pad/{pad_slot}")
    def edit_pad(
        request: Request,
        kit_index: int,
        pad_slot: int,
        volume_a: int = Form(...),
        volume_b: int = Form(0),
        pitch_a: int = Form(...),
        pitch_b: int = Form(0),
        pan_a: int = Form(...),
        pan_b: int = Form(0),
        muffling_a: int = Form(...),
        muffling_b: int = Form(0),
        ambient_a: int = Form(...),
        ambient_b: int = Form(0),
        sweep_a: int = Form(...),
        sweep_b: int = Form(0),
        patch_a: int = Form(...),
        patch_b: int = Form(0),
    ):
        _bounds_check_kit(kit_index)
        _bounds_check_pad(pad_slot)
        hpd = state.require()
        pad = hpd.pads.get_pad(kit_index * PADS_PER_KIT + pad_slot)
        pad.set_volume(0, _clamp(volume_a, 0, 100))
        pad.set_volume(1, _clamp(volume_b, 0, 100))
        pad.set_pitch(0, _clamp(pitch_a, -2400, 2400))
        pad.set_pitch(1, _clamp(pitch_b, -2400, 2400))
        pad.set_pan(0, _clamp(pan_a, -15, 15))
        pad.set_pan(1, _clamp(pan_b, -15, 15))
        pad.set_muffling(0, _clamp(muffling_a, 0, 100))
        pad.set_muffling(1, _clamp(muffling_b, 0, 100))
        pad.set_ambientsend(0, _clamp(ambient_a, 0, 127))
        pad.set_ambientsend(1, _clamp(ambient_b, 0, 127))
        pad.set_sweep(0, _clamp(sweep_a, -100, 100))
        pad.set_sweep(1, _clamp(sweep_b, -100, 100))
        pad.set_patch(0, patch_a)
        pad.set_patch(1, patch_b)
        state.mark_dirty()
        if request.headers.get("HX-Request"):
            return _render_pad_fragment(request, templates, state, kit_index, pad_slot)
        return RedirectResponse(f"/kit/{kit_index}/pad/{pad_slot}", status_code=303)

    @app.post("/kit/{kit_index}/pad/{pad_slot}/patch")
    def apply_patch(
        request: Request,
        kit_index: int,
        pad_slot: int,
        layer: int = Form(0),
        instrument_id: int = Form(...),
    ):
        """Apply a single instrument to one layer without touching other fields."""
        _bounds_check_kit(kit_index)
        _bounds_check_pad(pad_slot)
        if layer not in (0, 1):
            raise HTTPException(400, "layer must be 0 or 1")
        hpd = state.require()
        pad = hpd.pads.get_pad(kit_index * PADS_PER_KIT + pad_slot)
        pad.set_patch(layer, instrument_id)
        state.mark_dirty()
        if request.headers.get("HX-Request"):
            return _render_pad_fragment(request, templates, state, kit_index, pad_slot)
        return RedirectResponse(f"/kit/{kit_index}/pad/{pad_slot}", status_code=303)

    @app.post("/kit/{kit_index}/pad-swap/{a_slot}/{b_slot}")
    def swap_pads_in_kit(kit_index: int, a_slot: int, b_slot: int):
        """Swap two pad slots (e.g. M1 <-> M2) within the current kit."""
        _bounds_check_kit(kit_index)
        _bounds_check_pad(a_slot)
        _bounds_check_pad(b_slot)
        hpd = state.require()
        hpd.swap_pads_in_kit(kit_index, a_slot, b_slot)
        state.mark_dirty()
        return RedirectResponse(f"/kit/{kit_index}/pad/{a_slot}", status_code=303)

    @app.get("/api/instruments")
    def api_instruments(q: str = ""):
        """All instruments + favourite flag, optionally filtered by substring."""
        fav_set = set(favorites.load())
        needle = q.strip().lower()
        items = []
        for idx, (_pitch, name) in INSTRUMENT_TABLE.items():
            if needle and needle not in name.lower():
                continue
            items.append({
                "id": idx,
                "name": name,
                "favorite": idx in fav_set,
            })
        return JSONResponse({"items": items, "favorites": sorted(fav_set)})

    @app.post("/api/favorites/{instrument_id}")
    def api_toggle_favorite(instrument_id: int):
        ids = favorites.toggle(instrument_id)
        return JSONResponse({"favorites": ids})

    @app.post("/kit/{kit_index}/name")
    def edit_kit_name(kit_index: int, main: str = Form(""), sub: str = Form("")):
        _bounds_check_kit(kit_index)
        hpd = state.require()
        kit = hpd.kits.get_kit(kit_index)
        kit.set_main_name(main)
        kit.set_sub_name(sub)
        state.mark_dirty()
        return RedirectResponse(f"/kit/{kit_index}", status_code=303)

    @app.post("/kit/{src}/copy/{dst}")
    def copy_kit(src: int, dst: int):
        _bounds_check_kit(src)
        _bounds_check_kit(dst)
        hpd = state.require()
        hpd.copy_kit(src, dst)
        state.mark_dirty()
        return RedirectResponse(f"/kit/{dst}", status_code=303)

    @app.post("/kit/{a}/swap/{b}")
    def swap_kits(a: int, b: int):
        _bounds_check_kit(a)
        _bounds_check_kit(b)
        hpd = state.require()
        hpd.swap_kits(a, b)
        state.mark_dirty()
        return RedirectResponse(f"/kit/{a}", status_code=303)

    @app.post("/save")
    def save(dest: str = Form("")):
        hpd = state.require()
        target = Path(dest) if dest else state.backup_path
        if target is None:
            raise HTTPException(400, "No destination path given")
        hpd.save(target)
        state.dirty = False
        return RedirectResponse("/", status_code=303)

    @app.get("/download")
    def download():
        hpd = state.require()
        if state.backup_path is None:
            raise HTTPException(400, "No source path on record")
        tmp = Path("/tmp") / f"edited_{state.backup_path.name}"
        hpd.save(tmp)
        return FileResponse(
            tmp,
            media_type="application/octet-stream",
            filename=state.backup_path.name,
        )

    return app


def _bounds_check_kit(kit_index: int) -> None:
    if not 0 <= kit_index < 200:
        raise HTTPException(404, f"kit {kit_index} out of range (0..199)")


def _bounds_check_pad(pad_slot: int) -> None:
    if not 0 <= pad_slot < PADS_PER_KIT:
        raise HTTPException(404, f"pad slot {pad_slot} out of range (0..{PADS_PER_KIT - 1})")


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _render_kit(
    request: Request,
    templates: Jinja2Templates,
    state: AppState,
    kit_index: int,
    selected_pad: int = 0,
):
    hpd = state.require()
    kit = hpd.kits.get_kit(kit_index)
    pads: list[dict[str, Any]] = []
    for slot in range(PADS_PER_KIT):
        pad = hpd.pads.get_pad(kit_index * PADS_PER_KIT + slot)
        summary = _pad_summary(pad, slot)
        # merge static SVG geometry with per-kit pad data
        geom = PAD_GEOMETRIES[slot]
        pads.append({**geom, **summary, "selected": slot == selected_pad})
    return templates.TemplateResponse(
        request,
        "kit.html",
        {
            "kit_index": kit_index,
            "kit_number": kit_index + 1,
            "kit_main": kit.main_name().strip(),
            "kit_sub": kit.sub_name().strip(),
            "kit_volume": kit.get_volume(),
            "kit_hh_volume": kit.get_hh_volume(),
            "kit_balance": kit.get_balance(),
            "pads": pads,
            "selected_pad": selected_pad,
            "pad_ctx": _pad_form_context(state, kit_index, selected_pad),
            "backup_name": state.backup_path.name if state.backup_path else "",
            "dirty": state.dirty,
            "skin_view_w": VIEW_W,
            "skin_view_h": VIEW_H,
            "all_kits": [
                f"{i + 1:>3}  {hpd.kits.get_kit(i).main_name().strip()}"
                for i in range(200)
            ],
        },
    )


def _render_pad_fragment(
    request: Request,
    templates: Jinja2Templates,
    state: AppState,
    kit_index: int,
    pad_slot: int,
):
    """Return just the pad-editor form, for HTMX swaps."""
    return templates.TemplateResponse(
        request,
        "_pad_form.html",
        {"pad_ctx": _pad_form_context(state, kit_index, pad_slot)},
    )


def _pad_form_context(state: AppState, kit_index: int, pad_slot: int) -> dict[str, Any]:
    hpd = state.require()
    pad = hpd.pads.get_pad(kit_index * PADS_PER_KIT + pad_slot)
    return {
        "kit_index": kit_index,
        "kit_number": kit_index + 1,
        "pad_slot": pad_slot,
        "pad_name": PAD_NAMES[pad_slot],
        "volume_a": pad.get_volume(0),
        "volume_b": pad.get_volume(1),
        "pitch_a": pad.get_pitch(0),
        "pitch_b": pad.get_pitch(1),
        "pan_a": pad.get_pan(0),
        "pan_b": pad.get_pan(1),
        "muffling_a": pad.get_muffling(0),
        "muffling_b": pad.get_muffling(1),
        "ambient_a": pad.get_ambientsend(0),
        "ambient_b": pad.get_ambientsend(1),
        "sweep_a": pad.get_sweep(0),
        "sweep_b": pad.get_sweep(1),
        "patch_a": pad.get_patch(0),
        "patch_b": pad.get_patch(1),
        "patch_a_name": get_instrument_name(pad.get_patch(0)),
        "patch_b_name": get_instrument_name(pad.get_patch(1)),
        "instruments": get_complete_instrument_list(),
    }


def _truncate(name: str, n: int) -> str:
    return name if len(name) <= n else name[: n - 1] + "…"


def _pad_summary(pad, slot: int) -> dict[str, Any]:
    raw_pitch = pad.get_pitch(0)
    absolute = raw_pitch + get_instrument_pitch(pad.get_patch(0))
    patch_name = get_instrument_name(pad.get_patch(0))
    # Character budget per family — Big-pad labels get ~14 chars, S-wedges ~8,
    # aux chips ~12. These track the CSS font sizes so names wrap gracefully.
    if slot < 5:
        short = _truncate(patch_name, 14)
    elif slot < 13:
        short = _truncate(patch_name, 8)
    else:
        short = _truncate(patch_name, 12)
    return {
        "slot": slot,
        "name": PAD_NAMES[slot],
        "layer": pad.get_layer(),
        "volume_a": pad.get_volume(0),
        "pitch_a": raw_pitch,
        "note_a": get_note_name((absolute + 50) / 100),
        "patch_name": patch_name,
        "patch_short": short,
        "pan_a": pad.get_pan(0),
        "active": pad.get_layer() > 0,
    }


def run(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = list(argv if argv is not None else sys.argv[1:])

    host = "127.0.0.1"
    port = 8000
    backup = None
    positional: list[str] = []
    while args:
        arg = args.pop(0)
        if arg == "--host":
            host = args.pop(0)
        elif arg == "--port":
            port = int(args.pop(0))
        elif arg in {"-h", "--help"}:
            print("usage: hpd20-web [--host HOST] [--port N] [BACKUP.HS0]")
            return 0
        elif arg.startswith("-"):
            print(f"unknown flag: {arg}")
            return 2
        else:
            positional.append(arg)

    if positional:
        backup = Path(positional[0])
        if not backup.exists():
            print(f"error: {backup} not found")
            return 2

    import uvicorn

    app = create_app(backup)
    log.info("serving at http://%s:%d (backup=%s)", host, port, backup)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
