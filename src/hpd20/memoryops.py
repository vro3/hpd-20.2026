"""Low-level big-endian read/write primitives for the HPD-20 memory layout."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class MemoryOp:
    @staticmethod
    def get_int8(mem_view, index: int) -> int:
        value = mem_view[index]
        return value - 256 if value > 127 else value

    @staticmethod
    def set_int8(mem_view, index: int, value: int) -> None:
        new = value & 0xFF
        if mem_view[index] != new:
            log.debug("set_int8 [%d] %d -> %d", index, mem_view[index], new)
            mem_view[index] = new

    @staticmethod
    def get_unsigned_int8(mem_view, index: int) -> int:
        return mem_view[index]

    @staticmethod
    def get_int16(mem_view, index: int) -> int:
        value = (mem_view[index] << 8) | mem_view[index + 1]
        return value - 65536 if value > 32767 else value

    @staticmethod
    def set_int16(mem_view, index: int, value: int) -> None:
        mem_view[index] = (value >> 8) & 0xFF
        mem_view[index + 1] = value & 0xFF

    @staticmethod
    def get_unsigned_int16(mem_view, index: int) -> int:
        return (mem_view[index] << 8) | mem_view[index + 1]

    @staticmethod
    def set_unsigned_int16(mem_view, index: int, value: int) -> None:
        mem_view[index] = (value >> 8) & 0xFF
        mem_view[index + 1] = value & 0xFF

    @staticmethod
    def get_string(mem_view, index: int, size: int) -> str:
        if index < 0 or index + size > len(mem_view):
            raise ValueError("Index and size out of bounds")
        chars: list[str] = []
        for i in range(index, index + size):
            b = mem_view[i]
            if b == 0:
                break
            chars.append(chr(b))
        return "".join(chars)

    @staticmethod
    def set_string(mem_view, index: int, string: str) -> None:
        encoded = string.encode("utf-8") + b"\x00"
        if index < 0 or index + len(encoded) > len(mem_view):
            raise ValueError("Index and encoded string length out of bounds")
        mem_view[index : index + len(encoded)] = encoded
