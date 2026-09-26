#!/usr/bin/env bash
# Start the Lunar Orbiter viewer on the host and port set in config.json.
#
# Creates .venv on first use. If an earlier instance of this viewer still holds
# the port it is stopped first; any other program on the port is left alone.
set -euo pipefail

cd "$(dirname "$0")/.."
python=.venv/bin/python

if [[ ! -x "$python" ]]; then
    echo "Creating .venv and installing the viewer…"
    python3 -m venv .venv
    "$python" -m pip install --quiet --upgrade pip
    "$python" -m pip install --quiet -e .
fi

port=$("$python" -c 'from orbiter.config import load_config; print(load_config().port)')

holders=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
for pid in $holders; do
    command=$(ps -o args= -p "$pid" || true)
    if [[ "$command" == *"orbiter.app"* || "$command" == *"lunar-orbiter"* ]]; then
        echo "Stopping previous viewer (PID $pid) on port $port"
        kill "$pid"
        for _ in $(seq 20); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.25
        done
    else
        echo "Port $port is in use by another program: $command" >&2
        echo "Change \"port\" in config.json or stop that program." >&2
        exit 1
    fi
done

exec "$python" -m orbiter.app
