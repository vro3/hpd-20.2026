"""Per-pad parameters (2-layer).

Each pad occupies 68 bytes. Offsets are from the pad header; layer B adds
1 byte to 8-bit fields and 2 bytes to 16-bit fields.
"""

from __future__ import annotations

from .memoryops import MemoryOp

PAD_MEMSIZE = 68


class Pad:
    VOL_INDEX = 0
    AMB_INDEX = 2
    PATCH_INDEX = 4
    PATCH_INTERNAL_INDEX = 8
    PITCH_INDEX = 12
    MUFFLING_INDEX = 16
    PAN_INDEX = 18
    COLOR_INDEX = 23
    MFX_ASSIGN_INDEX = 25
    SWEEP_INDEX = 27
    MIDI_INDEX = 33
    MIDI_GATE_INDEX = 34
    SEND_ALL_PADS_INDEX = 36
    SEND_TO_KIT_INDEX = 37
    REC_PITCH_INDEX = 39
    MUTE_INDEX = 40
    RT_PITCH_INDEX = 41
    ROLL_INDEX = 42
    LAYER_INDEX = 43
    FADE_VALUE_INDEX = 44
    TRIGGER_INDEX = 45
    FIX_VELOCITY_INDEX = 47
    FIX_GROUP_INDEX = 48
    MONO_POLY_INDEX = 49

    def __init__(self, memory_block, index: int):
        self.memory_block = memory_block
        self.index = index

    def get_volume(self, layer: int) -> int:
        return self.memory_block[self.index + Pad.VOL_INDEX + layer]

    def set_volume(self, layer: int, value: int) -> None:
        self.memory_block[self.index + Pad.VOL_INDEX + layer] = value & 0xFF

    def get_pan(self, layer: int) -> int:
        return MemoryOp.get_int8(self.memory_block, self.index + Pad.PAN_INDEX + layer)

    def set_pan(self, layer: int, value: int) -> None:
        MemoryOp.set_int8(self.memory_block, self.index + Pad.PAN_INDEX + layer, value)

    def get_color(self, layer: int) -> int:
        return self.memory_block[self.index + Pad.COLOR_INDEX + layer]

    def set_color(self, layer: int, value: int) -> None:
        self.memory_block[self.index + Pad.COLOR_INDEX + layer] = value & 0xFF

    def get_sweep(self, layer: int) -> int:
        return MemoryOp.get_int8(self.memory_block, self.index + Pad.SWEEP_INDEX + layer)

    def set_sweep(self, layer: int, value: int) -> None:
        MemoryOp.set_int8(self.memory_block, self.index + Pad.SWEEP_INDEX + layer, value)

    def get_ambientsend(self, layer: int) -> int:
        return self.memory_block[self.index + Pad.AMB_INDEX + layer]

    def set_ambientsend(self, layer: int, value: int) -> None:
        self.memory_block[self.index + Pad.AMB_INDEX + layer] = value & 0xFF

    def get_muffling(self, layer: int) -> int:
        return self.memory_block[self.index + Pad.MUFFLING_INDEX + layer]

    def set_muffling(self, layer: int, value: int) -> None:
        self.memory_block[self.index + Pad.MUFFLING_INDEX + layer] = value & 0xFF

    def get_patch(self, layer: int) -> int:
        return MemoryOp.get_unsigned_int16(
            self.memory_block, self.index + Pad.PATCH_INDEX + layer * 2
        )

    def set_patch(self, layer: int, patch_number: int) -> None:
        MemoryOp.set_unsigned_int16(
            self.memory_block, self.index + Pad.PATCH_INDEX + layer * 2, patch_number
        )

    def get_internal_patch(self, layer: int) -> int:
        return MemoryOp.get_unsigned_int16(
            self.memory_block, self.index + Pad.PATCH_INTERNAL_INDEX + layer * 2
        )

    def set_internal_patch(self, layer: int, value: int) -> None:
        MemoryOp.set_unsigned_int16(
            self.memory_block, self.index + Pad.PATCH_INTERNAL_INDEX + layer * 2, value
        )

    def get_pitch(self, layer: int) -> int:
        return MemoryOp.get_int16(
            self.memory_block, self.index + Pad.PITCH_INDEX + layer * 2
        )

    def set_pitch(self, layer: int, pitch: int) -> None:
        MemoryOp.set_int16(
            self.memory_block, self.index + Pad.PITCH_INDEX + layer * 2, pitch
        )

    def get_midi(self) -> int:
        return self.memory_block[self.index + Pad.MIDI_INDEX]

    def set_midi(self, value: int) -> None:
        self.memory_block[self.index + Pad.MIDI_INDEX] = value & 0xFF

    def get_layer(self) -> int:
        return self.memory_block[self.index + Pad.LAYER_INDEX]

    def set_layer(self, value: int) -> None:
        self.memory_block[self.index + Pad.LAYER_INDEX] = value & 0xFF

    def get_velofade(self) -> int:
        return self.memory_block[self.index + Pad.FADE_VALUE_INDEX]

    def set_velofade(self, value: int) -> None:
        self.memory_block[self.index + Pad.FADE_VALUE_INDEX] = value & 0xFF

    def get_trigger(self) -> int:
        return self.memory_block[self.index + Pad.TRIGGER_INDEX]

    def set_trigger(self, value: int) -> None:
        self.memory_block[self.index + Pad.TRIGGER_INDEX] = value & 0xFF

    def get_fixvelo(self) -> int:
        return self.memory_block[self.index + Pad.FIX_VELOCITY_INDEX]

    def set_fixvelo(self, value: int) -> None:
        self.memory_block[self.index + Pad.FIX_VELOCITY_INDEX] = value & 0xFF

    def get_mute_group(self) -> int:
        return self.memory_block[self.index + Pad.FIX_GROUP_INDEX]

    def set_mute_group(self, value: int) -> None:
        self.memory_block[self.index + Pad.FIX_GROUP_INDEX] = value & 0xFF

    def get_mono_poly(self) -> int:
        return self.memory_block[self.index + Pad.MONO_POLY_INDEX]

    def set_mono_poly(self, value: int) -> None:
        self.memory_block[self.index + Pad.MONO_POLY_INDEX] = value & 0xFF

    def save(self, fh) -> None:
        fh.write(bytes(self.memory_block[self.index : self.index + PAD_MEMSIZE]))

    def load(self, fh) -> None:
        data = fh.read(PAD_MEMSIZE)
        if len(data) != PAD_MEMSIZE:
            raise ValueError(f"expected {PAD_MEMSIZE} bytes, got {len(data)}")
        self.memory_block[self.index : self.index + PAD_MEMSIZE] = data


class Pads:
    PAD_NAMES = (
        "M1", "M2", "M3", "M4", "M5",
        "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
        "D-Beam", "Head", "Rim", "HH",
    )

    def __init__(self, memory_block, index_from: int, index_to: int):
        self.indexFrom = index_from
        self.memory_block = memory_block
        self.pads = [Pad(memory_block, index_from + PAD_MEMSIZE * i) for i in range(17 * 200)]

    def get_pad_name(self, index: int) -> str:
        return Pads.PAD_NAMES[index]

    def get_pad(self, index: int) -> Pad:
        return self.pads[index]
