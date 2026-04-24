HPD-20 Editor
=============

Patch editor and librarian for the **Roland HPD-20 HandSonic**.

Works on the binary memory-dump files (``BKUP-###.HS0``) you pull off a USB
stick — the HPD-20 has no MIDI SysEx, so this file-edit workflow is the
only way to script changes.

Fork of `scjurgen/hpd-20 <https://github.com/scjurgen/hpd-20>`_ by
Jürgen Schwietering. He did the reverse-engineering; this fork modernizes
the stack and adds a browser-based UI.


Install
-------

Requires Python 3.10+.  From a checkout::

    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[web,dev]"


CLI usage
---------

::

    hpd20-cli BKUP-021.HS0 show kits
    hpd20-cli BKUP-021.HS0 show kit 5


Web UI
------

::

    hpd20-web BKUP-021.HS0

Then open http://localhost:8000. The "device view" shows a visual of the
HPD-20 pad layout — click any pad to edit it. The "grid view" is a
spreadsheet-style matrix for bulk edits.


Workflow
--------

1. On the HPD-20: **SYS-USB → Memory → Backup (without user instruments)**
2. Copy the ``BKUP-###.HS0`` file from the USB stick to your computer
3. Open it in the editor, make changes, save to a file with the same
   naming pattern (001-100: ``BKUP-002.HS0``)
4. Copy back to the USB stick, restore on the device

**Don't overwrite your original backup — save a copy.**


Development
-----------

::

    pip install -e ".[dev]"
    pytest
    ruff check src tests
    mypy src/hpd20


Credits
-------

- **Jürgen Schwietering** — original implementation, memory-format
  reverse-engineering, instrument database
- **Vince Romanelli** — 2026 fork: modernization, web UI, tests

See ``docs/JURGEN-NOTES.rst`` for the original roadmap and
``docs/planning/`` for the modernization plan.
