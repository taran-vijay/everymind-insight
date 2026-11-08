#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3.11 >/dev/null 2>&1; then
    python3.11 scripts/launch.py
    launch_status=$?
elif command -v uv >/dev/null 2>&1; then
    uv run --no-project --python 3.11 scripts/launch.py
    launch_status=$?
elif command -v python3 >/dev/null 2>&1; then
    python3 scripts/launch.py
    launch_status=$?
else
    echo 'Install Python 3.11 from https://www.python.org/downloads/ then reopen this launcher.'
    launch_status=1
fi
printf '\nPress Enter to close…'
read -r answer || true
exit "$launch_status"
