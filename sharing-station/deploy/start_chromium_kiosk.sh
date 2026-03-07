#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://localhost:8000/}"

CHROMIUM_BIN="$(command -v chromium-browser || true)"
if [[ -z "${CHROMIUM_BIN}" ]]; then
  CHROMIUM_BIN="$(command -v chromium || true)"
fi

if [[ -z "${CHROMIUM_BIN}" ]]; then
  echo "Chromium not found. Install chromium-browser first." >&2
  exit 1
fi

exec "${CHROMIUM_BIN}" \
  --kiosk \
  --incognito \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --use-fake-ui-for-media-stream \
  "${URL}"
