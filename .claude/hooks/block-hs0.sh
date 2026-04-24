#!/bin/bash
# PreToolUse hook: prevent Edit/Write on the bundled BKUP-*.HS0 test fixtures.
# Exit code 2 blocks the tool call and surfaces the message to Claude.

set -u

fp=$(python3 -c "import json,sys;
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
print(d.get('tool_input', {}).get('file_path', ''))" 2>/dev/null)

case "$fp" in
    *BKUP-*.HS0)
        echo "BLOCKED: $fp is a golden-file test fixture. Modifying it would break tests/test_roundtrip.py. Write a new file elsewhere (e.g. /tmp/edited.HS0) and leave the bundled backups pristine." >&2
        exit 2
        ;;
esac
exit 0
