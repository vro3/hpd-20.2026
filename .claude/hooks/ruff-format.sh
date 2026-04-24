#!/bin/bash
# PostToolUse hook: auto-format + auto-fix Python files after Edit/Write.
# Reads the tool-call JSON from stdin, extracts file_path, formats if .py.
# Silent on success; failures don't block the tool call.

set -u
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

fp=$(python3 -c "import json,sys;
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
print(d.get('tool_input', {}).get('file_path', ''))" 2>/dev/null)

[[ -n "$fp" && "$fp" == *.py ]] || exit 0
[ -x .venv/bin/ruff ] || exit 0

.venv/bin/ruff format "$fp" >/dev/null 2>&1 || true
.venv/bin/ruff check --fix "$fp" >/dev/null 2>&1 || true
exit 0
