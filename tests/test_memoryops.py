"""Byte-level read/write primitives."""

from __future__ import annotations

import pytest

from hpd20.memoryops import MemoryOp


@pytest.fixture
def block() -> bytearray:
    return bytearray(i % 256 for i in range(512))


class TestMemoryOp:
    def test_fetch_8bit(self, block):
        assert MemoryOp.get_unsigned_int8(block, 1) == 1
        assert MemoryOp.get_unsigned_int8(block, 129) == 129
        assert MemoryOp.get_int8(block, 255) == -1

    def test_write_8bit(self, block):
        MemoryOp.set_int8(block, 1, 2)
        assert MemoryOp.get_unsigned_int8(block, 1) == 2
        MemoryOp.set_int8(block, 129, -6)
        assert MemoryOp.get_unsigned_int8(block, 129) == 250
        assert MemoryOp.get_int8(block, 129) == -6

    def test_fetch_16bit(self, block):
        assert MemoryOp.get_unsigned_int16(block, 1) == 258
        assert MemoryOp.get_unsigned_int16(block, 254) == 65279
        assert MemoryOp.get_int16(block, 254) == -257

    def test_write_16bit(self, block):
        MemoryOp.set_int16(block, 1, -2)
        assert MemoryOp.get_int16(block, 1) == -2
        MemoryOp.set_unsigned_int16(block, 1, 0x8990)
        assert MemoryOp.get_unsigned_int16(block, 1) == 0x8990

    def test_fetch_string(self, block):
        assert MemoryOp.get_string(block, 48, 8) == "01234567"

    def test_write_string(self, block):
        MemoryOp.set_string(block, 48, "foobar??")
        assert MemoryOp.get_string(block, 48, 8) == "foobar??"
        MemoryOp.set_string(block, 54, "!!")
        assert MemoryOp.get_string(block, 48, 8) == "foobar!!"
