#!/bin/sh
set -eu

# Virtual display for Playwright headed mode in containers (publish / profile checks).
if [ -z "${DISPLAY:-}" ]; then
  export DISPLAY=:99
fi

if ! pgrep -x Xvfb >/dev/null 2>&1; then
  Xvfb "${DISPLAY}" -screen 0 1280x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
