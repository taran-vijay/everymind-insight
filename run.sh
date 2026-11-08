#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3.11 >/dev/null 2>&1; then
    exec python3.11 scripts/launch.py --judge
elif command -v uv >/dev/null 2>&1; then
    exec uv run --no-project --python 3.11 scripts/launch.py --judge
elif command -v python3 >/dev/null 2>&1; then
    exec python3 scripts/launch.py --judge
else
    echo 'Install Python 3.11 from https://www.python.org/downloads/ and run this command again.'
    exit 1
fi
