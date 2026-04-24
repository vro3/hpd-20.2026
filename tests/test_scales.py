"""Scale and note math."""

from __future__ import annotations

from hpd20.scales import Scale


class TestScale:
    def test_scale_height(self):
        assert Scale.get_height_of_note("C4") == 60
        assert Scale.get_height_of_note("C3") == 48

    def test_root_notes_list(self):
        roots = Scale.get_root_notes()
        assert roots[0] == "C2"
        assert len(roots) % 12 == 1

    def test_scale_generation_major(self):
        scale = Scale.get_scale("Balaphone", 60, 5, "major", Scale.IONIAN)
        assert scale[2][1] == -800

    def test_scale_generation_minor(self):
        scale = Scale.get_scale("Balaphone", 60, 5, "minor", Scale.IONIAN)
        assert scale[2][1] == -900

    def test_note_naming(self):
        assert Scale.get_note_name(60) == "C4"
