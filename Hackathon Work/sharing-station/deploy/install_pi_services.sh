#!/usr/bin/env bash
set -euo pipefail

# Installs:
# - sharing-station-backend.service (FastAPI + WebRTC token endpoints)
# - sharing-station-kiosk.service  (Chromium kiosk on local dashboard)
#
# Usage:
#   ./deploy/install_pi_services.sh
#   ./deploy/install_pi_services.sh pi

TARGET_USER="${1:-${SUDO_USER:-${USER}}}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/venv/bin/python"
KIOSK_SCRIPT="${PROJECT_DIR}/deploy/start_chromium_kiosk.sh"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python venv binary not found at ${PYTHON_BIN}" >&2
  echo "Create the virtualenv in sharing-station/venv before installing services." >&2
  exit 1
fi

if [[ ! -x "${KIOSK_SCRIPT}" ]]; then
  echo "Kiosk script missing or not executable: ${KIOSK_SCRIPT}" >&2
  exit 1
fi

BACKEND_SERVICE_PATH="/etc/systemd/system/sharing-station-backend.service"
KIOSK_SERVICE_PATH="/etc/systemd/system/sharing-station-kiosk.service"

echo "Installing services for user: ${TARGET_USER}"
echo "Project dir: ${PROJECT_DIR}"

sudo tee "${BACKEND_SERVICE_PATH}" >/dev/null <<EOF
[Unit]
Description=Sharing Station Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
Environment=VOICE_RUNTIME=webrtc
ExecStart=${PYTHON_BIN} -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

sudo tee "${KIOSK_SERVICE_PATH}" >/dev/null <<EOF
[Unit]
Description=Sharing Station Chromium Kiosk
After=graphical.target sharing-station-backend.service
Wants=graphical.target sharing-station-backend.service

[Service]
Type=simple
User=${TARGET_USER}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${TARGET_USER}/.Xauthority
ExecStartPre=/bin/sleep 8
ExecStart=${KIOSK_SCRIPT} http://localhost:8000/
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sharing-station-backend.service
sudo systemctl enable sharing-station-kiosk.service
sudo systemctl restart sharing-station-backend.service
sudo systemctl restart sharing-station-kiosk.service

echo
echo "Installed and started:"
echo "  - sharing-station-backend.service"
echo "  - sharing-station-kiosk.service"
echo
echo "Check status with:"
echo "  sudo systemctl status sharing-station-backend.service"
echo "  sudo systemctl status sharing-station-kiosk.service"
