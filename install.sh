#!/usr/bin/env bash
# ByteForge Installer — works on any Linux distro (systemd or not)
set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  RED='\033[0;31m' GRN='\033[0;32m' YLW='\033[1;33m'
  ORG='\033[38;5;208m' BLD='\033[1m' RST='\033[0m'
else
  RED='' GRN='' YLW='' ORG='' BLD='' RST=''
fi

STEP=0
step() { STEP=$((STEP+1)); echo -e "\n${ORG}[${STEP}]${RST} ${BLD}$*${RST}"; }
ok()   { echo -e "  ${GRN}✓${RST}  $*"; }
warn() { echo -e "  ${YLW}!${RST}  $*"; }
die()  { echo -e "\n${RED}ERROR:${RST} $*\n" >&2; exit 1; }

# ── Config ─────────────────────────────────────────────────────────────────
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/ByteForge"
TARGET_DIR="${BYTEFORGE_INSTALL_DIR:-/opt/byteforge}"
PORT="${BYTEFORGE_PORT:-8080}"

# ── Privilege helper ───────────────────────────────────────────────────────
run_p() { [ "${EUID:-$(id -u)}" -eq 0 ] && "$@" || sudo "$@"; }

# ── Banner ─────────────────────────────────────────────────────────────────
echo -e "
${ORG}  ██████╗ ██╗   ██╗████████╗███████╗${RST}
${ORG}  ██╔══██╗╚██╗ ██╔╝╚══██╔══╝██╔════╝${RST}
${ORG}  ██████╔╝ ╚████╔╝    ██║   █████╗  ${RST}
${ORG}  ██╔══██╗  ╚██╔╝     ██║   ██╔══╝  ${RST}
${ORG}  ██████╔╝   ██║      ██║   ███████╗${RST}
${ORG}  ╚═════╝    ╚═╝      ╚═╝   ╚══════╝${RST}
${ORG}  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗${RST}
${ORG}  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝${RST}
${ORG}  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  ${RST}
${ORG}  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  ${RST}
${ORG}  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗${RST}
${ORG}  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝${RST}

  ${BLD}Homelab Control Panel — Linux Installer${RST}
"

# ── Source files check ─────────────────────────────────────────────────────
[ -f "$SRC_DIR/byteforge-server.py" ] || die "ByteForge source files not found in $SRC_DIR\nRun this script from the ByteForge repo root."

# ── Detect package manager ─────────────────────────────────────────────────
detect_pkg_manager() {
  if   command -v apt-get  >/dev/null 2>&1; then echo apt
  elif command -v dnf      >/dev/null 2>&1; then echo dnf
  elif command -v yum      >/dev/null 2>&1; then echo yum
  elif command -v pacman   >/dev/null 2>&1; then echo pacman
  elif command -v zypper   >/dev/null 2>&1; then echo zypper
  elif command -v apk      >/dev/null 2>&1; then echo apk
  elif command -v emerge   >/dev/null 2>&1; then echo emerge
  else echo unknown
  fi
}

pkg_install() {
  local pkg="$1"
  local pm
  pm="$(detect_pkg_manager)"
  case "$pm" in
    apt)    run_p apt-get install -y "$pkg" ;;
    dnf)    run_p dnf install -y "$pkg" ;;
    yum)    run_p yum install -y "$pkg" ;;
    pacman) run_p pacman -Sy --noconfirm "$pkg" ;;
    zypper) run_p zypper install -y "$pkg" ;;
    apk)    run_p apk add "$pkg" ;;
    emerge) run_p emerge "$pkg" ;;
    *)      die "Could not detect a package manager. Install $pkg manually and re-run." ;;
  esac
}

# ── Ensure Python 3 ────────────────────────────────────────────────────────
ensure_python() {
  if command -v python3 >/dev/null 2>&1; then
    ok "Python 3 found: $(python3 --version)"
    PYTHON_BIN="$(command -v python3)"
    return
  fi
  warn "Python 3 not found — installing..."
  local pm
  pm="$(detect_pkg_manager)"
  case "$pm" in
    apt)    run_p apt-get install -y python3 ;;
    dnf)    run_p dnf install -y python3 ;;
    yum)    run_p yum install -y python3 ;;
    pacman) run_p pacman -Sy --noconfirm python ;;
    zypper) run_p zypper install -y python3 ;;
    apk)    run_p apk add python3 ;;
    emerge) run_p emerge dev-lang/python ;;
    *)      die "Cannot install Python 3 automatically. Install it manually and re-run." ;;
  esac
  command -v python3 >/dev/null 2>&1 || die "Python 3 install failed."
  PYTHON_BIN="$(command -v python3)"
  ok "Python 3 installed: $(python3 --version)"
}

# ── Ensure curl ────────────────────────────────────────────────────────────
ensure_curl() {
  command -v curl >/dev/null 2>&1 && return
  warn "curl not found — installing..."
  pkg_install curl
  ok "curl installed."
}

# ── Install Docker ─────────────────────────────────────────────────────────
ensure_docker() {
  if command -v docker >/dev/null 2>&1; then
    ok "Docker found: $(docker --version)"
    # Make sure the daemon is running
    if command -v systemctl >/dev/null 2>&1; then
      run_p systemctl enable --now docker >/dev/null 2>&1 || true
    fi
    return
  fi
  warn "Docker not found."
  if [ -t 0 ]; then
    read -rp "  Install Docker automatically? [Y/n] " ans
    [[ "${ans:-y}" =~ ^[Nn] ]] && { warn "Skipping Docker. Game servers and apps won't work without it."; return; }
  fi
  ensure_curl
  warn "Downloading Docker installer from get.docker.com..."
  curl -fsSL https://get.docker.com | run_p sh
  if command -v systemctl >/dev/null 2>&1; then
    run_p systemctl enable --now docker
  fi
  # Add current user to docker group so they don't need sudo for docker commands
  if [ "${EUID:-$(id -u)}" -ne 0 ] && id -nG "$USER" | grep -qv docker; then
    run_p usermod -aG docker "$USER" && warn "Added $USER to docker group. You may need to log out and back in."
  fi
  ok "Docker installed: $(docker --version)"
}

# ── Password setup ─────────────────────────────────────────────────────────
prompt_password() {
  if [ -n "${BYTEFORGE_ADMIN_PASSWORD:-}" ]; then
    ok "Using password from environment variable."
    return
  fi
  if [ ! -t 0 ]; then
    die "Set BYTEFORGE_ADMIN_PASSWORD or run this script in an interactive terminal."
  fi
  echo -e "  Choose a login password for the ${BLD}ADMIN${RST} account:"
  while true; do
    read -rsp "  Password (min 8 chars): " BYTEFORGE_ADMIN_PASSWORD; echo
    read -rsp "  Confirm password:       " confirm;                   echo
    [ "${#BYTEFORGE_ADMIN_PASSWORD}" -lt 8 ] && { warn "Password must be at least 8 characters."; continue; }
    [ "$BYTEFORGE_ADMIN_PASSWORD" != "$confirm" ] && { warn "Passwords do not match."; continue; }
    break
  done
  export BYTEFORGE_ADMIN_PASSWORD
  ok "Password set."
}

# ── Check for upgrade ──────────────────────────────────────────────────────
check_existing() {
  UPGRADING=0
  if [ -f "$TARGET_DIR/byteforge-server.py" ]; then
    warn "ByteForge is already installed at $TARGET_DIR."
    if [ -t 0 ]; then
      read -rp "  Upgrade existing install? [Y/n] " ans
      if [[ "${ans:-y}" =~ ^[Nn] ]]; then echo "Aborted."; exit 0; fi
    else
      warn "Non-interactive mode — upgrading automatically."
    fi
    ok "Upgrading existing install."
    UPGRADING=1
  fi
}

# ── Port check ─────────────────────────────────────────────────────────────
check_port() {
  if command -v ss >/dev/null 2>&1; then
    if ss -tlnH 2>/dev/null | grep -q ":${PORT} "; then
      warn "Port $PORT is already in use. Set BYTEFORGE_PORT=<other> and re-run."
    fi
  fi
}

# ── Copy files ─────────────────────────────────────────────────────────────
install_files() {
  run_p mkdir -p "$TARGET_DIR"
  for f in byteforge-server.py byteforge-platform.html byteforge-platform.css byteforge-platform.js byteforge-logo.svg byteforge-icon.svg; do
    [ -f "$SRC_DIR/$f" ] && run_p cp "$SRC_DIR/$f" "$TARGET_DIR/$f"
  done
  # Copy api/ package directory (required since server.py was split into modules)
  if [ -d "$SRC_DIR/api" ]; then
    run_p mkdir -p "$TARGET_DIR/api"
    run_p cp -r "$SRC_DIR/api/." "$TARGET_DIR/api/"
  fi
  ok "Files copied to $TARGET_DIR"
}

# ── systemd service ────────────────────────────────────────────────────────
install_systemd() {
  local pw
  pw="$(printf '%s' "$BYTEFORGE_ADMIN_PASSWORD" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  run_p tee /etc/systemd/system/byteforge.service >/dev/null <<EOF
[Unit]
Description=ByteForge Platform
After=network.target

[Service]
Type=simple
WorkingDirectory=$TARGET_DIR
ExecStart=$PYTHON_BIN $TARGET_DIR/byteforge-server.py
Restart=always
RestartSec=5
Environment="BYTEFORGE_PORT=$PORT"
Environment="BYTEFORGE_ADMIN_PASSWORD=$pw"

[Install]
WantedBy=multi-user.target
EOF
  run_p systemctl daemon-reload
  run_p systemctl enable byteforge
  run_p systemctl restart byteforge
  ok "systemd service enabled and started."
}

# ── Fallback: startup script (non-systemd) ─────────────────────────────────
install_fallback() {
  local start_script="$TARGET_DIR/start.sh"
  run_p tee "$start_script" >/dev/null <<EOF
#!/usr/bin/env bash
export BYTEFORGE_PORT="$PORT"
export BYTEFORGE_ADMIN_PASSWORD="$BYTEFORGE_ADMIN_PASSWORD"
exec "$PYTHON_BIN" "$TARGET_DIR/byteforge-server.py"
EOF
  run_p chmod +x "$start_script"
  ok "Startup script written to $start_script"

  # Try rc.local if it exists
  if [ -f /etc/rc.local ]; then
    if ! grep -q byteforge /etc/rc.local; then
      run_p sed -i "s|^exit 0|$start_script \&\nexit 0|" /etc/rc.local
      ok "Added to /etc/rc.local (starts on boot)."
    fi
  fi

  warn "systemd not found. To start ByteForge now, run:"
  warn "  sudo $start_script &"
}

# ── Get local IPs ──────────────────────────────────────────────────────────
local_ips() {
  ip -4 addr show 2>/dev/null | awk '/inet / && !/127\./ {print $2}' | cut -d/ -f1 | head -5 || \
  hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -5
}

# ── Main ───────────────────────────────────────────────────────────────────
main() {
  # Require Linux for this script
  [ "$(uname -s)" = "Linux" ] || die "This script is for Linux only. Use install.ps1 on Windows."

  step "Checking for existing install"
  check_existing
  check_port

  step "Checking Python 3"
  ensure_python

  step "Checking Docker"
  ensure_docker

  step "Setting admin password"
  if [ "${UPGRADING:-0}" -eq 1 ] && [ -z "${BYTEFORGE_ADMIN_PASSWORD:-}" ]; then
    # On upgrade, keep existing password from the service file if possible
    existing_pw="$(grep -oP '(?<=BYTEFORGE_ADMIN_PASSWORD=).*' /etc/systemd/system/byteforge.service 2>/dev/null | head -1 || true)"
    if [ -n "$existing_pw" ]; then
      BYTEFORGE_ADMIN_PASSWORD="$existing_pw"
      export BYTEFORGE_ADMIN_PASSWORD
      ok "Keeping existing admin password."
    else
      prompt_password
    fi
  else
    prompt_password
  fi

  step "Installing ByteForge files"
  install_files

  step "Setting up service"
  if command -v systemctl >/dev/null 2>&1 && systemctl --quiet is-system-running 2>/dev/null || \
     command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    install_systemd
  else
    install_fallback
  fi

  # ── Done ────────────────────────────────────────────────────────────────
  echo -e "\n${ORG}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
  echo -e "  ${GRN}${BLD}ByteForge installed successfully!${RST}"
  echo -e "${ORG}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n"
  echo -e "  ${BLD}Open in browser:${RST}"
  echo -e "    http://127.0.0.1:${PORT}"
  while IFS= read -r ip; do
    echo -e "    http://${ip}:${PORT}"
  done < <(local_ips)
  echo
  echo -e "  ${BLD}Login:${RST}  username = ADMIN"
  echo -e "  ${BLD}Logs:${RST}   sudo journalctl -u byteforge -f"
  echo -e "  ${BLD}Update:${RST} bash $ROOT_DIR/deploy.sh"
  echo
}

main "$@"
