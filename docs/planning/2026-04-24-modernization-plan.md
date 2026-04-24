---
status: proposed
date: 2026-04-24
author: Vince + Claude
outcome:
lessons:
---

# HPD-20 Editor — Deep Audit & Modernization Plan

## Context

Jürgen Schwietering's `scjurgen/hpd-20` (forked at `vro3/hpd-20.2026`) is a
patch editor/librarian for the Roland HPD-20 HandSonic. The HPD-20 cannot be
edited over MIDI (no SysEx published), so the editor works on the binary
memory dump files (`BKUP-###.HS0`, 282,812 bytes) you pull off a USB stick.

Last meaningful commit: **2024-11-14**. Last architectural change: 2020
("update to python 3.8"). Single author. No releases, no tags, no CI, GUI
depends on wxPython which no longer installs cleanly on modern macOS.

The good news: the **core is solid**.  On Python 3.14 today, loading a real
backup, listing all 200 kits, inspecting per-pad parameters, and round-tripping
the file byte-for-byte (MD5 intact) all work out of the box.

## Audit findings

### What works today (verified on Python 3.14.3)

- `hpd20-cli show kits` / `show kit N` — lists all 200 kits, pad patches, volume, pitch.  ✅
- Load → re-save round-trip is byte-identical, MD5 checksum matches.  ✅
- Scale math (`Scale.get_scale`, root-note lookup, mode shifting).  ✅
- Memory-ops unit tests: **10/10 pass**. Scales tests: **4/4 pass**.  ✅
- Kit export is already complete — the repo ships 110 pre-extracted `.kit` files.  ✅

### What's broken or rotten

1. **GUI doesn't run** — `wxPython` is not installed and is notoriously fragile
   on Apple Silicon + Python 3.14. ([hpd20/hpd20wx.py](hpd20/hpd20wx.py))
2. **`Pad.load()` is broken** — calls `fh.readinto(68)` which passes an int
   where a buffer is required; never actually exercised.
   ([hpd20/pad.py:135-137](hpd20/pad.py#L135))
3. **`pads_unittests.py` crashes** — stale test calls `Pads(memory_block)`
   with one arg, ctor needs three. ([hpd20/pads_unittests.py:13](hpd20/pads_unittests.py#L13))
4. **`read_scl.py` is Python 2** — uses builtin `file()`, broken on Python 3.
   ([hpd20/read_scl.py:9](hpd20/read_scl.py#L9))
5. **Debug noise in prod** — `MemoryOp.set_int8` prints every byte change to
   stdout. ([hpd20/memoryops.py:14-17](hpd20/memoryops.py#L14))
6. **Empty / dead files** — `chain.py` (0 bytes), `ratios.py` (7-line snippet),
   `cp-mac-test.sh` (author's local helper), `pack.sh`.
7. **Flat imports break `python -m`** — `from pad import Pads` only works when
   `hpd20/` is the cwd. Should be `from .pad import Pads`. All modules.
8. **Hard-coded fallback** — `HpdForm('Backup/BKUP-022.HS0')` in
   [hpd20/hpd20wx.py:303](hpd20/hpd20wx.py#L303).
9. **Setup metadata stale** — Python 2.7 shebangs in `instrumentname.py` &
   `ethnic_scales.py`; `install_requires=['configparser', ...]` (configparser
   is stdlib in Py3); only declares Python 3.8 support.
10. **Roadmap gaps (README)**: scale on instrument B, copy/swap kits, MFX
    editing, pan-over-pad-set, L↔R swap macros, chain editing — all `(x) = todo`.

### Binary-format knowledge (already captured)

The C reference in [c-code/main.cpp](c-code/main.cpp) and offsets in
[hpd20/hpd20.py:35-47](hpd20/hpd20.py#L35) give the full layout:
- Chains: 15 × 128 bytes @ 1180
- Kits: 200 × 224 bytes @ 6922  (name @ +2, subname @ +14, vol @ +30, HH vol @ +31, balance @ +67, pad-sens @ +55)
- Pads: 3400 × 68 bytes @ 51596  (2-layer: volume, ambient, patch, pitch, muffling, pan, colour, sweep, mfx)
- MD5-16 appended at EOF

Unknown bytes remain in the kit/pad blocks (MFX routing is the biggest unknown).

## Recommended approach

Five phases. Phase 0 + 1 are safe cleanup and can land today; Phase 2 is the
new GUI and is a decision point; Phase 3-4 extend features.

### Phase 0 — Stabilize (half day)

Goal: what exists runs cleanly on Python 3.11+ with modern tooling.

- [ ] Convert to a proper package: `src/hpd20/` layout, relative imports
      (`from .pad import Pads`).
- [ ] Replace `setup.py` with `pyproject.toml` (`hatchling` or `setuptools`
      ≥ 61). Drop stdlib `configparser` from requires. Declare Python ≥ 3.10.
- [ ] Delete dead code: `chain.py` (empty), `ratios.py`, `cp-mac-test.sh`,
      `pack.sh` (or move to `/scripts` if still useful).
- [ ] Silence `MemoryOp.set_int8` — swap prints for a module-level `logger`
      at DEBUG level.
- [ ] Fix `Pad.load` — use `fh.readinto(memoryview(self.memory_block)[…])`
      pattern, with a covering test.
- [ ] Add `ruff` config + format pass. Add `mypy --strict` on the domain
      modules (not the UI).

### Phase 1 — Test harness & CI (half day)

Goal: no regression can hide in future changes.

- [ ] Migrate `*_unittests.py` → `tests/` with `pytest`.
- [ ] Use the bundled `BKUP-021.HS0` and `BKUP-058.HS0` as **golden fixtures**:
  - Load → digest → compare against frozen text snapshot
  - Load → save → byte-for-byte equal, MD5 equal
  - Extract all 200 kits → hash-compare to pre-extracted `kits/*.kit`
  - Fix the broken `pads_unittests.py`
- [ ] GitHub Actions: `pytest` + `ruff` + `mypy` on macOS + Ubuntu, Python
      3.10/3.11/3.12/3.13.
- [ ] Coverage gate (`pytest-cov`, 80% on domain modules).

### Phase 2 — New GUI  *(decision needed)*

Drop wxPython. Three realistic paths, in order of recommendation:

#### Option A — **PySide6 (Qt for Python)**  [recommended]
Modern, installs cleanly on Apple Silicon, native look, excellent grid widgets
(good for the per-pad parameter matrix), first-class dark mode, easy scale
dialogs. License is LGPL. Installs via `pip install PySide6`.
*Cost:* ~40 MB download, one new dep.

#### Option B — **Browser UI (FastAPI + HTMX + Alpine)**
Run a local server, edit in your browser. Easy to iterate, shareable to iPad
for live use, trivial to screenshot/record. Keep the Python domain layer as
the single source of truth; UI is thin HTML.
*Cost:* slightly less "native" feel, needs a local server running.

#### Option C — **Tkinter / ttk**  [fallback]
Stdlib, no install. Good enough for a utility. Used to be the README's
original plan.  Already ugly on macOS without theme work; skip unless you
want zero dependencies.

The domain code (`kit.py`, `pad.py`, `memoryops.py`, `scales.py`) doesn't
care which UI we pick — it's already pure logic.

**My recommendation: Option A (PySide6).** Reasons: you're building a patch
editor, Qt's Model/View + `QTableView` is perfect for the 17-pad × 15-column
grid the current wx code is trying to build; font + color rendering on
macOS is native; and we get signals/slots for live preview of scale
changes.

If you want to share the app with other HPD-20 users later, **Option B**
(browser) starts to look attractive too. Let me know.

### Phase 3 — Feature completion (1-2 days)

Based on the README roadmap:

- [ ] **Copy / swap kits** between slots. Trivial given 224-byte block + 17 pads.
- [ ] **Scale on instrument B** (currently only layer A).
- [ ] **Chain editor** — 15 chains × 128 bytes. C struct is in [main.cpp:4-9](c-code/main.cpp#L4); decode + UI is small.
- [ ] **Pan-over-pad-set** macro (already drafted per roadmap).
- [ ] **L↔R swap** macro (M1↔M2, S1↔S8, etc.).
- [ ] **Better pad diffing** — show what changed after a macro, before save.

### Phase 4 — Stretch (reverse-engineering territory)

- [ ] **MFX editing** — biggest unknown block. Needs diff-testing: change one
      MFX parameter on device, snapshot backup, compare bytes. Time-intensive
      but tractable. Could use /loop for systematic byte-diffing.
- [ ] **Kit library / catalog** — publishable .kit catalogue with tags,
      descriptions, compatibility notes.
- [ ] **Printable kit sheet** — README explicitly calls out "print your
      settings on some paper for live performances."  PDF via `reportlab`.

## Critical files

To stabilize (Phase 0-1), the files that change:
- [hpd20/memoryops.py](hpd20/memoryops.py) — remove debug prints
- [hpd20/pad.py](hpd20/pad.py) — fix `load()`
- [hpd20/hpd20.py](hpd20/hpd20.py) — relative imports, drop unused `mkdir`
- [hpd20/hpd20wx.py](hpd20/hpd20wx.py) — delete after Phase 2 replacement
- [hpd20/pads_unittests.py](hpd20/pads_unittests.py) — fix ctor args
- [hpd20/read_scl.py](hpd20/read_scl.py) — port to Py3 or delete
- [setup.py](setup.py) / [requirements.txt](requirements.txt) → `pyproject.toml`
- *new:* `tests/test_roundtrip.py`, `tests/test_digest_snapshots.py`
- *new:* `.github/workflows/ci.yml`

## Done when

- [ ] `pip install -e .` works on Python 3.10-3.13 without touching system libs
- [ ] `pytest` passes, >80% coverage on domain modules
- [ ] `hpd20-cli show kits /path/to/BKUP-021.HS0` runs as before
- [ ] New GUI launches with `hpd20-gui` and opens a backup file
- [ ] CI green on macOS + Linux
- [ ] Round-trip byte-equality test in CI, MD5 verified
- [ ] README updated with install + quickstart

## Verification plan

- `pytest` — golden-file round-trip against the two bundled backups
- Manual: launch GUI, open `BKUP-021.HS0`, browse kits, edit a volume, save
  to `/tmp/out.HS0`, re-open, confirm change persisted, load onto device
- `diff` of `kits/*.kit` against freshly-exported kits (should be identical)

## Questions for Vince

1. **GUI choice** — PySide6 (native desktop, recommended) or browser (FastAPI + HTMX)?
2. **Scope for this pass** — want me to run Phases 0 + 1 now as a safe starting cleanup, or hold for your go-ahead?
3. **MFX reverse-engineering** — is editing effects a "must have" or "nice to have"?
4. **Publishing** — do you want this as its own fork under `vro3/` once it's solid, or keep it personal?

## Not doing (yet)

- Touching the HPD-20 over USB/MIDI — module doesn't expose SysEx, confirmed.
- Rewriting `ethnic_scales.py` (4407 lines of data) — it's fine as data.
- Touching `instrumentname.py`'s 1745-line dict except to add the Py2 shebang fix.
