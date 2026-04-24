---
name: hpd20-domain
description: Roland HPD-20 HandSonic binary memory-dump layout — kit/pad/chain offsets, pad families, MIDI note defaults, MD5 trailer, instrument index ranges. Load when modifying src/hpd20/core.py, pad.py, kit.py, memoryops.py, skin_geometry.py, or midi/engine.py. Also load when writing tests that inspect pad/kit/chain bytes or when the user asks about memory layout, byte offsets, or the HPD-20's internal format. Skip for pure UI/CSS/HTML work.
user-invocable: false
---

# HPD-20 Domain Knowledge

The HPD-20 exposes no MIDI SysEx, so all editing happens on the binary memory
dump (``BKUP-###.HS0``) exported from the device's USB stick. The device
accepts restored dumps only if the trailing MD5 matches the payload.

## File format (282 812 bytes total)

| Region   | Offset  | Size/item  | Count | Total       |
|----------|---------|-----------|-------|-------------|
| Header   | 0       | —         | —     | (fixed)     |
| Chains   | 1 180   | 128       | 15    | 1 920       |
| *(gap)*  | 3 100   | —         | —     | 3 822       |
| Kits     | 6 922   | 224       | 200   | 44 800      |
| *(gap)*  | 51 722  | —         | —     | (sparse)    |
| Pads     | 51 596  | 68        | 3 400 | 231 200     |
| *(gap)*  | ...     | —         | —     | (sparse)    |
| MD5      | 282 796 | 16        | 1     | 16          |

`Pads` count = `KITS_COUNT (200) × PADS_PER_KIT (17)`. Constants live in
[src/hpd20/core.py](src/hpd20/core.py).

## Kit struct (224 bytes)

| Field            | Offset | Type   | Notes |
|------------------|--------|--------|-------|
| Main name        | +2     | 12B    | null-terminated ASCII, max 11 chars |
| Sub name         | +14    | 16B    | null-terminated ASCII, max 15 chars |
| Volume           | +30    | u8     |       |
| HH volume        | +31    | u8     |       |
| Pad sensitivity  | +55    | i8     |       |
| Balance          | +67    | i8     |       |

## Pad struct (68 bytes, 2 layers)

| Field           | Offset | Per-layer stride | Range / notes |
|-----------------|--------|-----------------|---------------|
| Volume          | +0     | 1               | 0..100 |
| Ambient send    | +2     | 1               | 0..127 |
| Patch (user)    | +4     | 2 (big-endian)  | internal patch #, high byte first |
| Patch (device)  | +8     | 2               | echoed by device |
| Pitch           | +12    | 2 (i16 BE)      | cents, -2400..2400 |
| Muffling        | +16    | 1               | 0..100 |
| Pan             | +18    | 1 (i8)          | -15..15 |
| Colour          | +23    | 1               | 0..5 (device palette) |
| MFX assign      | +25    | 1               |  |
| Sweep           | +27    | 1 (i8)          | -100..100 |
| MIDI note       | +33    | 1 (shared)      | default 60..76 for M1..HH |
| MIDI gate       | +34    | 1               |  |
| Send all pads   | +36    | 1               |  |
| Send to kit     | +37    | 1               |  |
| Rec pitch       | +39    | 1               |  |
| Mute            | +40    | 1               |  |
| RT pitch        | +41    | 1               |  |
| Roll            | +42    | 1               |  |
| Layer mode      | +43    | 1               | 0 off, 1 mix, 2 velo-mix, 3 velo-fade, 4 velo-sw |
| Fade value      | +44    | 1               |  |
| Trigger mode    | +45    | 1               | 0 shot, 1 gate, 2 alt |
| Fix velocity    | +47    | 1               |  |
| Mute group      | +48    | 1               | 0..8 |
| Mono/poly       | +49    | 1               |  |

All multi-byte integers are **big-endian**. Signed 8-bit via
`MemoryOp.get_int8` (see [src/hpd20/memoryops.py](src/hpd20/memoryops.py)).

## Pad slot layout (17 slots per kit)

```
  0: M1    (main, bottom-left quadrant)
  1: M2    (main, bottom-right quadrant)
  2: M3    (main, top-left quadrant)
  3: M4    (main, top-right quadrant)
  4: M5    (main, centre small pad)
  5..12: S1..S8  (eight side wedges, top outer ring, left→right)
 13: D-Beam  (optical aux trigger)
 14: Head    (external trigger in)
 15: Rim     (external trigger in)
 16: HH      (hi-hat pedal)
```

Default MIDI notes: slots 0..16 → notes 60..76 (factory default; user can
reassign per pad via the MIDI byte).

## Instrument table

~850 sample slots live in `instruments` dict at
[src/hpd20/instrumentname.py](src/hpd20/instrumentname.py) keyed by
(patch_number → (default_pitch_cents, name)). Patches above ~850 are
user-recorded "User Instrument #N".

Melodic sets (used by the scale dialog) in
[src/hpd20/scales.py](src/hpd20/scales.py):

```
Steel Drum     348..355
Balaphone      356..359
Slit Drum      362..366
Gyilli         367..371
Lithophone     372..376
Khongwong      377..381
Kalimba        382..386
Santoor        387..395
Hand Pan       396..403
Tone Plate     404..408
Vibraphone     409..417
Marimba        418..427
Glockenspiel   428..433
Tubular Bells  434..435
```

## MD5 trailer

Last 16 bytes of the file are MD5 of bytes [0, -16). ``HPD.save`` in
[src/hpd20/core.py](src/hpd20/core.py) recomputes it on every write; if the
trailer doesn't match the device refuses to restore.

## Bundled test fixtures

- `BKUP-021.HS0` — factory-ish backup used in pytest golden-file tests.
- `BKUP-058.HS0` — second fixture for robustness.

**Both are checked into git.** Changing them breaks
``tests/test_roundtrip.py``. A PreToolUse hook blocks Edit/Write on
``BKUP-*.HS0`` — feature, not a bug.

## Common pitfalls

- **Endianness**: patches are *big-endian* u16; tools that assume little-endian
  read garbage patch numbers.
- **Kit-file format** (``.kit``): 224-byte kit header followed by 17 × 68-byte
  pads = 1 380 bytes. Not interchangeable with full backups.
- **MIDI byte vs. instrument patch**: the MIDI input note (offset +33) is
  independent of the patch number (+4). Editing one doesn't affect the other.
- **Device accepts edits**: save rewrites MD5 so restored dumps validate.
  Dropping or corrupting the trailer makes the device reject the file.
