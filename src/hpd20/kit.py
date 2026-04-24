"""Kit header: name, sub-name, per-kit volume / balance / sensitivity."""

from __future__ import annotations

from .memoryops import MemoryOp

KIT_MEMSIZE = 224

NAME_INDEX = 2
SUBNAME_INDEX = 14
VOL_INDEX = 30
HH_VOL_INDEX = 31
PAD_SENSITIVITY = 55
BALANCE_INDEX = 67


class Kit:
    def __init__(self, memory_block, index: int):
        self.index = index
        self.memory_block = memory_block

    def main_name(self) -> str:
        return MemoryOp.get_string(self.memory_block, self.index + NAME_INDEX, 12)

    def sub_name(self) -> str:
        return MemoryOp.get_string(self.memory_block, self.index + SUBNAME_INDEX, 16)

    def set_main_name(self, name: str) -> None:
        buf = name.encode("utf-8")[:11] + b"\x00"
        self.memory_block[self.index + NAME_INDEX : self.index + NAME_INDEX + len(buf)] = buf

    def set_sub_name(self, name: str) -> None:
        buf = name.encode("utf-8")[:15] + b"\x00"
        self.memory_block[self.index + SUBNAME_INDEX : self.index + SUBNAME_INDEX + len(buf)] = buf

    def get_volume(self) -> int:
        return MemoryOp.get_unsigned_int8(self.memory_block, self.index + VOL_INDEX)

    def get_hh_volume(self) -> int:
        return MemoryOp.get_unsigned_int8(self.memory_block, self.index + HH_VOL_INDEX)

    def get_balance(self) -> int:
        return MemoryOp.get_int8(self.memory_block, self.index + BALANCE_INDEX)

    def get_pad_sensitvity(self) -> int:
        return MemoryOp.get_int8(self.memory_block, self.index + PAD_SENSITIVITY)

    def save(self, fh) -> None:
        fh.write(bytes(self.memory_block[self.index : self.index + KIT_MEMSIZE]))

    def load(self, fh) -> None:
        data = fh.read(KIT_MEMSIZE)
        if len(data) != KIT_MEMSIZE:
            raise ValueError(f"expected {KIT_MEMSIZE} bytes, got {len(data)}")
        self.memory_block[self.index : self.index + KIT_MEMSIZE] = data


class Kits:
    def __init__(self, memory_block, index_from: int, index_to: int):
        self.indexFrom = index_from
        self.indexTo = index_to
        self.memory_block = memory_block
        self.kits = [Kit(memory_block, index_from + KIT_MEMSIZE * i) for i in range(200)]

    def get_list_of_kits(self) -> list[str]:
        return [f"{i + 1} {k.main_name().strip()}" for i, k in enumerate(self.kits)]

    def get_kit(self, index: int) -> Kit:
        return self.kits[index]
