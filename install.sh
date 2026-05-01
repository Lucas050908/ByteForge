#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/ByteForge"
OS_NAME="$(uname -s)"
PORT="${BYTEFORGE_PORT:-8080}"

if [ "$OS_NAME" = "Darwin" ]; then
  TARGET_DIR="${BYTEFORGE_INSTALL_DIR:-/usr/local/byteforge}"
else
  TARGET_DIR="${BYTEFORGE_INSTALL_DIR:-/opt/byteforge}"
fi

need_sudo() {
  [ "${EUID:-$(id -u)}" -ne 0 ] && command -v sudo >/dev/null 2>&1
}

run_privileged() {
  if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

prompt_admin_password() {
  if [ -n "${BYTEFORGE_ADMIN_PASSWORD:-}" ]; then
    return
  fi
  if [ ! -t 0 ]; then
    echo "Set BYTEFORGE_ADMIN_PASSWORD or run this installer in an interactive terminal."
    exit 1
  fi
  while true; do
    read -rsp "Choose ByteForge ADMIN password: " BYTEFORGE_ADMIN_PASSWORD
    echo
    read -rsp "Confirm ByteForge ADMIN password: " confirm
    echo
    if [ "${#BYTEFORGE_ADMIN_PASSWORD}" -lt 8 ]; then
      echo "Password must be at least 8 characters."
    elif [ "$BYTEFORGE_ADMIN_PASSWORD" != "$confirm" ]; then
      echo "Passwords do not match."
    else
      export BYTEFORGE_ADMIN_PASSWORD
      unset confirm
      break
    fi
  done
}

systemd_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

xml_escape() {
  printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g'
}

copy_files() {
  if [ ! -f "$SRC_DIR/byteforge-server.py" ]; then
    echo "ByteForge files not found in $SRC_DIR"
    exit 1
  fi
  run_privileged mkdir -p "$TARGET_DIR"
  for file in byteforge-server.py byteforge-platform.html byteforge-platform.css byteforge-platform.js byteforge-logo.svg byteforge-icon.svg; do
    if [ -f "$SRC_DIR/$file" ]; then
      run_privileged cp "$SRC_DIR/$file" "$TARGET_DIR/$file"
    fi
  done
}

python_bin() {
  command -v python3 || command -v python || {
    echo "Python 3 is required."
    exit 1
  }
}

install_docker_linux() {
  if command -v docker >/dev/null 2>&1; then
    echo "[OK] Docker already installed."
    return
  fi
  if [ -t 0 ]; then
    read -rp "Docker is not installed. Install Docker now? [y/N] " answer
    case "$answer" in
      y|Y|yes|YES) ;;
      *) echo "Skipping Docker install."; return ;;
    esac
  fi
  curl -fsSL https://get.docker.com | run_privileged sh
  if command -v systemctl >/dev/null 2>&1; then
    run_privileged systemctl enable --now docker
  fi
}

install_docker_macos() {
  if command -v docker >/dev/null 2>&1; then
    echo "[OK] Docker CLI already installed."
    return
  fi
  if [ -t 0 ]; then
    read -rp "Docker Desktop is not installed. Install with Homebrew now? [y/N] " answer
    case "$answer" in
      y|Y|yes|YES) ;;
      *) echo "Install Docker Desktop later from https://www.docker.com/products/docker-desktop/"; return ;;
    esac
  fi
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Install Docker Desktop manually from https://www.docker.com/products/docker-desktop/"
    return
  fi
  brew install --cask docker
  echo "Open Docker.app once after install so the Docker engine starts."
}

install_systemd() {
  local py="$1"
  local password
  password="$(systemd_escape "$BYTEFORGE_ADMIN_PASSWORD")"
  run_privileged tee /etc/systemd/system/byteforge.service >/dev/null <<EOF
[Unit]
Description=ByteForge Platform
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
WorkingDirectory=$TARGET_DIR
ExecStart=$py $TARGET_DIR/byteforge-server.py
Restart=always
RestartSec=5
Environment="BYTEFORGE_PORT=$PORT"
Environment="BYTEFORGE_ADMIN_PASSWORD=$password"

[Install]
WantedBy=multi-user.target
EOF
  run_privileged systemctl daemon-reload
  run_privileged systemctl enable --now byteforge
}

install_launchd() {
  local py="$1"
  local password
  password="$(xml_escape "$BYTEFORGE_ADMIN_PASSWORD")"
  local py_xml target_xml port_xml
  py_xml="$(xml_escape "$py")"
  target_xml="$(xml_escape "$TARGET_DIR/byteforge-server.py")"
  port_xml="$(xml_escape "$PORT")"
  run_privileged tee /Library/LaunchDaemons/com.byteforge.server.plist >/dev/null <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.byteforge.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>$py_xml</string>
    <string>$target_xml</string>
  </array>
  <key>WorkingDirectory</key><string>$(xml_escape "$TARGET_DIR")</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>BYTEFORGE_PORT</key><string>$port_xml</string>
    <key>BYTEFORGE_ADMIN_PASSWORD</key><string>$password</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/byteforge.log</string>
  <key>StandardErrorPath</key><string>/tmp/byteforge.err</string>
</dict>
</plist>
EOF
  run_privileged launchctl unload /Library/LaunchDaemons/com.byteforge.server.plist >/dev/null 2>&1 || true
  run_privileged launchctl load -w /Library/LaunchDaemons/com.byteforge.server.plist
}

main() {
  echo "ByteForge terminal installer"
  prompt_admin_password
  copy_files
  local py
  py="$(python_bin)"

  case "$OS_NAME" in
    Linux)
      install_docker_linux
      if command -v systemctl >/dev/null 2>&1; then
        install_systemd "$py"
        echo "ByteForge installed as a systemd service."
      else
        echo "systemd not found. Files installed to $TARGET_DIR."
        echo "Run: BYTEFORGE_ADMIN_PASSWORD='***' BYTEFORGE_PORT=$PORT $py $TARGET_DIR/byteforge-server.py"
      fi
      ;;
    Darwin)
      install_docker_macos
      install_launchd "$py"
      echo "ByteForge installed as a launchd service."
      ;;
    *)
      echo "Unsupported OS for install.sh: $OS_NAME"
      exit 1
      ;;
  esac

  echo
  echo "Open: http://127.0.0.1:$PORT"
  echo "Login username: ADMIN"
}

main "$@"
