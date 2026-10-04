#!/bin/bash
# Decodes a recording (README.md): with no argument the newest in logs/, or: bash decode.command logs/<recording>
args=()
for a in "$@"; do
    args+=("$(cd "$(dirname "$a")" && pwd)/$(basename "$a")")
done
cd "$(dirname "$0")" || exit 1
PY=python3
if .venv/bin/python -c '' 2>/dev/null; then
    PY=.venv/bin/python
fi
exec "$PY" trace_decode.py "${args[@]}"
