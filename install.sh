#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="inwx-robot.service"
TIMER_FILE="inwx-robot.timer"
SYSTEMD_DIR="/etc/systemd/system"

if [[ ! -f "$SCRIPT_DIR/config.default.py" ]]; then
  echo "Fehler: config.default.py wurde nicht gefunden in $SCRIPT_DIR"
  exit 1
fi

if [[ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]]; then
  echo "Fehler: $SERVICE_FILE wurde nicht gefunden in $SCRIPT_DIR"
  exit 1
fi

if [[ ! -f "$SCRIPT_DIR/$TIMER_FILE" ]]; then
  echo "Fehler: $TIMER_FILE wurde nicht gefunden in $SCRIPT_DIR"
  exit 1
fi

if [[ -f "$SCRIPT_DIR/config.py" ]]; then
  echo "config.py existiert bereits, ueberspringe Kopie."
else
  cp "$SCRIPT_DIR/config.default.py" "$SCRIPT_DIR/config.py"
  echo "config.default.py wurde nach config.py kopiert."
fi

echo "Installiere systemd Unit-Dateien mit sudo..."
sudo install -m 0644 "$SCRIPT_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_FILE"
sudo install -m 0644 "$SCRIPT_DIR/$TIMER_FILE" "$SYSTEMD_DIR/$TIMER_FILE"

echo "Lade systemd neu..."
sudo systemctl daemon-reload

echo "Aktiviere und starte Service und Timer..."
sudo systemctl enable --now inwx-robot.service
sudo systemctl enable --now inwx-robot.timer

echo "Pruefe Status..."
sudo systemctl status --no-pager inwx-robot.service || true
sudo systemctl status --no-pager inwx-robot.timer || true

echo "Installation abgeschlossen."
