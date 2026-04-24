"""MIDI I/O for the HPD-20 editor.

Optional import — the rest of the app works without it if the ``midi`` extra
isn't installed.
"""

from .engine import MidiEngine, MidiEvent, MidiUnavailable

__all__ = ["MidiEngine", "MidiEvent", "MidiUnavailable"]
