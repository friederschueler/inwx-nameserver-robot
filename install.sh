#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="inwx-nameserver-robot.service"
TIMER_FILE="inwx-nameserver-robot.timer"
SYSTEMD_DIR="/etc/systemd/system"

if [[ ! -f "$SCRIPT_DIR/config.default.py" ]]; then
  echo "Error: config.default.py not found in $SCRIPT_DIR"
  exit 1
fi

if [[ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]]; then
  echo "Error: $SERVICE_FILE not found in $SCRIPT_DIR"
  exit 1
fi

if [[ ! -f "$SCRIPT_DIR/$TIMER_FILE" ]]; then
  echo "Error: $TIMER_FILE not found in $SCRIPT_DIR"
  exit 1
fi

# --- Create system user ---
if id "inwx-nameserver-robot" &>/dev/null; then
  echo "System user 'inwx-nameserver-robot' already exists, skipping."
else
  echo "Creating system user 'inwx-nameserver-robot'..."
  sudo useradd \
    --system \
    --no-create-home \
    --shell /usr/sbin/nologin \
    --comment "INWX Nameserver Robot" \
    inwx-nameserver-robot
  echo "System user 'inwx-nameserver-robot' created."
fi

# --- Populate config.py ---
if [[ -f "$SCRIPT_DIR/config.py" ]]; then
  echo "config.py already exists, skipping configuration."
else
  echo ""
  echo "=== Configuration ==="

  read -rp "INWX username: " CFG_USERNAME
  read -rsp "INWX password: " CFG_PASSWORD
  echo ""
  read -rp "Domain (e.g. example.com): " CFG_DOMAIN

  echo "Enter record names as a comma-separated list."
  echo "Leave empty for root domain (@), e.g.: ,www,mail"
  read -rp "RECORD_NAMES: " CFG_RECORD_NAMES_RAW

  # Convert comma-separated input to a Python list, e.g. ",www" -> ["", "www"]
  CFG_RECORD_NAMES_PY="[$(echo "$CFG_RECORD_NAMES_RAW" | sed 's/,/", "/g' | sed 's/^/"/;s/$/"/' | sed 's/""/"/g')]"

  read -rp "Network interface (default: eno1): " CFG_INTERFACE
  CFG_INTERFACE="${CFG_INTERFACE:-eno1}"

  cp "$SCRIPT_DIR/config.default.py" "$SCRIPT_DIR/config.py"

  sed -i \
    -e "s|INWX_USERNAME = \"your_username\"|INWX_USERNAME = \"${CFG_USERNAME}\"|" \
    -e "s|INWX_PASSWORD = \"your_password\"|INWX_PASSWORD = \"${CFG_PASSWORD}\"|" \
    -e "s|DOMAIN = \"example.com\"|DOMAIN = \"${CFG_DOMAIN}\"|" \
    -e "s|RECORD_NAMES = \[\"\".*\]|RECORD_NAMES = ${CFG_RECORD_NAMES_PY}|" \
    -e "s|INTERFACE = \"eno1\"|INTERFACE = \"${CFG_INTERFACE}\"|" \
    "$SCRIPT_DIR/config.py"

  echo "config.py has been created and populated."
fi

# --- Deploy application files ---
INSTALL_DIR="/opt/inwx-robot"

echo "Deploying application files to $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp "$SCRIPT_DIR/main.py" "$INSTALL_DIR/main.py"
sudo cp "$SCRIPT_DIR/config.py" "$INSTALL_DIR/config.py"

# --- Create virtual environment ---
if [[ -d "$INSTALL_DIR/venv" ]]; then
  echo "Virtual environment already exists, skipping."
else
  echo "Creating virtual environment..."
  sudo python3 -m venv "$INSTALL_DIR/venv"
  echo "Installing dependencies..."
  sudo "$INSTALL_DIR/venv/bin/pip" install --quiet requests
  echo "Virtual environment ready."
fi

# --- Set ownership ---
echo "Setting ownership to inwx-nameserver-robot:inwx-nameserver-robot..."
sudo chown -R inwx-nameserver-robot:inwx-nameserver-robot "$INSTALL_DIR"

echo "Installing systemd unit files..."
sudo install -m 0644 "$SCRIPT_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_FILE"
sudo install -m 0644 "$SCRIPT_DIR/$TIMER_FILE" "$SYSTEMD_DIR/$TIMER_FILE"

echo "Reloading systemd..."
sudo systemctl daemon-reload

echo "Enabling and starting timer..."
sudo systemctl enable --now inwx-nameserver-robot.timer

echo "Checking status..."
sudo systemctl status --no-pager inwx-nameserver-robot.service || true
sudo systemctl status --no-pager inwx-nameserver-robot.timer || true

echo "Installation complete."
