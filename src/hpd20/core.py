"""HPD-20 memory dump model: kits, pads, chains."""

from __future__ import annotations

import hashlib
import logging
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from .instrumentname import get_instrument_name, get_instrument_pitch
from .kit import Kits
from .pad import Pads
from .scales import Scale

log = logging.getLogger(__name__)


CHAIN_MEMINDEX = 1180
CHAIN_MEMSIZE = 128

KIT_MEMINDEX = 6922
KIT_MEMSIZE = 224

PAD_MEMINDEX = 51596
PAD_MEMSIZE = 68

CHAINS_COUNT = 15
PADS_PER_KIT = 17
KITS_COUNT = 200
PADS_COUNT = KITS_COUNT * PADS_PER_KIT

PAD_NAMES = (
    "M1", "M2", "M3", "M4", "M5",
    "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8",
    "D-Beam", "Head", "Rim", "HH",
)

NOTE_NAMES = (" C", "C#", " D", "Eb", " E", " F", "F#", " G", "Ab", " A", "Bb", " B")


def get_note_name(value: float) -> str:
    if value < 0:
        return "--"
    n = int(value)
    return NOTE_NAMES[n % 12] + str(int((n - 24) / 12))


class HPD:
    """Loaded HPD-20 memory dump.

    The trailing 16 bytes are an MD5 of the preceding payload; :py:meth:`save`
    rewrites the MD5 so edits are accepted when restored on the device.
    """

    CHAIN_MEMINDEX = CHAIN_MEMINDEX
    CHAIN_MEMSIZE = CHAIN_MEMSIZE
    KIT_MEMINDEX = KIT_MEMINDEX
    KIT_MEMSIZE = KIT_MEMSIZE
    PAD_MEMINDEX = PAD_MEMINDEX
    PAD_MEMSIZE = PAD_MEMSIZE
    CHAINS_COUNT = CHAINS_COUNT
    PADS_PER_KIT = PADS_PER_KIT
    KITS_COUNT = KITS_COUNT
    PADS_COUNT = PADS_COUNT

    def __init__(self, file_path: str | Path):
        file_path = Path(file_path)
        log.info("loading %s", file_path)
        memory_block = bytearray(file_path.read_bytes())
        self.md5_memory = bytes(memory_block[-16:])
        self.memoryBlock = memory_block[:-16]
        self.kits = Kits(
            self.memoryBlock,
            KIT_MEMINDEX,
            KIT_MEMINDEX + KITS_COUNT * KIT_MEMSIZE,
        )
        self.pads = Pads(
            self.memoryBlock,
            PAD_MEMINDEX,
            PAD_MEMINDEX + PADS_COUNT * PAD_MEMSIZE,
        )

    def md5_matches(self) -> bool:
        return hashlib.md5(self.memoryBlock).digest() == self.md5_memory

    def digest_kits(self) -> str:
        out = ["Kits:"]
        for i in range(KITS_COUNT):
            k = self.kits.get_kit(i)
            out.append(f"{i + 1}:\t{k.main_name().strip()}\t{k.sub_name().strip()}")
        return "\n".join(out) + "\n"

    def digest_single_kit(self, kit_number: int) -> str:
        kit_index = kit_number - 1
        kit = self.kits.get_kit(kit_index)
        out = [f"Kit {kit_number}: {kit.main_name()} {kit.sub_name()}"]
        for i in range(PADS_PER_KIT):
            pad = self.pads.get_pad(kit_index * PADS_PER_KIT + i)
            raw = pad.get_pitch(0)
            absolute = raw + get_instrument_pitch(pad.get_patch(0))
            note = get_note_name((absolute + 50) / 100)
            out.append(
                f"{PAD_NAMES[i]}: {note} vol={pad.get_volume(0)} "
                f"{get_instrument_name(pad.get_patch(0))} pitch={raw}"
            )
        return "\n".join(out) + "\n"

    def save(self, file_path: str | Path) -> None:
        digest = hashlib.md5(self.memoryBlock).digest()
        Path(file_path).write_bytes(bytes(self.memoryBlock) + digest)

    save_file = save

    def save_kit(self, kit_index: int, file_path: str | Path) -> None:
        with open(file_path, "wb") as fh:
            self.kits.get_kit(kit_index).save(fh)
            for pad_slot in range(PADS_PER_KIT):
                self.pads.get_pad(PADS_PER_KIT * kit_index + pad_slot).save(fh)

    def load_kit(self, kit_index: int, file_path: str | Path) -> None:
        """Overwrite slot ``kit_index`` with the kit + pads from a .kit file."""
        with open(file_path, "rb") as fh:
            # Both Kit.load and Pad.load write directly into the shared memoryBlock
            # at the slot's offset, so no further copy is needed.
            self.kits.get_kit(kit_index).load(fh)
            for pad_slot in range(PADS_PER_KIT):
                self.pads.get_pad(PADS_PER_KIT * kit_index + pad_slot).load(fh)

    def kit_filename(self, kit_index: int, directory: str | Path = "kits") -> Path:
        kit = self.kits.get_kit(kit_index)
        name = kit.main_name().strip()
        sub = kit.sub_name().strip()
        if sub:
            name = f"{name} ({sub})"
        allowed = {"!", "&", "(", ")", "_", ".", "{", "}", " "}
        safe = "".join(c if c.isalnum() or c in allowed else "_" for c in name)
        return Path(directory) / f"{safe}.kit"

    create_kit_filename = kit_filename

    def save_all_kits(self, directory: str | Path = "kits") -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for i in range(KITS_COUNT):
            self.save_kit(i, self.kit_filename(i, directory))

    def apply_scale(
        self,
        layer: int,
        instrument_name: str,
        scale_name: str,
        mode: int,
        first_note: int,
        kit_index: int,
        pad_slots: Sequence[int],
    ) -> None:
        mapping = Scale.get_scale(instrument_name, first_note, len(pad_slots), scale_name, mode)
        for slot, (instrument_number, pitch_cents) in zip(pad_slots, mapping, strict=False):
            final = PADS_PER_KIT * kit_index + slot
            pad = self.pads.get_pad(final)
            pad.set_patch(layer, instrument_number)
            pad.set_pitch(layer, pitch_cents)

    def swap_kits(self, a: int, b: int) -> None:
        self._swap_block(KIT_MEMINDEX, KIT_MEMSIZE, a, b)
        for slot in range(PADS_PER_KIT):
            self._swap_block(
                PAD_MEMINDEX,
                PAD_MEMSIZE,
                a * PADS_PER_KIT + slot,
                b * PADS_PER_KIT + slot,
            )

    def copy_kit(self, src: int, dst: int) -> None:
        self._copy_block(KIT_MEMINDEX, KIT_MEMSIZE, src, dst)
        for slot in range(PADS_PER_KIT):
            self._copy_block(
                PAD_MEMINDEX,
                PAD_MEMSIZE,
                src * PADS_PER_KIT + slot,
                dst * PADS_PER_KIT + slot,
            )

    def _swap_block(self, base: int, size: int, a: int, b: int) -> None:
        off_a = base + size * a
        off_b = base + size * b
        tmp = bytes(self.memoryBlock[off_a : off_a + size])
        self.memoryBlock[off_a : off_a + size] = self.memoryBlock[off_b : off_b + size]
        self.memoryBlock[off_b : off_b + size] = tmp

    def _copy_block(self, base: int, size: int, src: int, dst: int) -> None:
        off_s = base + size * src
        off_d = base + size * dst
        self.memoryBlock[off_d : off_d + size] = self.memoryBlock[off_s : off_s + size]


# Kept for any old imports (``from hpd20 import hpd``)
hpd = HPD


def _usage(prog: str) -> None:
    print(f"usage: {prog} BACKUP.HS0 [show kits | show kit N]")


def run_main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"-h", "--help"}:
        _usage("hpd20-cli")
        return 0

    backup = HPD(args.pop(0))
    out: list[str] = []
    while args:
        op = args.pop(0)
        if op == "show" and args:
            what = args.pop(0)
            if what == "kits":
                out.append(backup.digest_kits())
            elif what == "kit" and args:
                out.append(backup.digest_single_kit(int(args.pop(0))))
        else:
            _usage("hpd20-cli")
            return 2
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(run_main())
