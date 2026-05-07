#!/usr/bin/env bash
# ByteForge Uninstaller — Linux & macOS
set -euo pipefail

# ── Colours ────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  RED='\033[0;31m' GRN='\033[0;32m' YLW='\033[1;33m'
  ORG='\033[38;5;208m' BLD='\033[1m' RST='\033[0m'
else
  RED='' GRN='' YLW='' ORG='' BLD='' RST=''
fi

ok()   { echo -e "  ${GRN}✓${RST}  $*"; }
warn() { echo -e "  ${YLW}!${RST}  $*"; }
info() { echo -e "  ${ORG}→${RST}  $*"; }
die()  { echo -e "\n${RED}ERROR:${RST} $*\n" >&2; exit 1; }

run_p() { [ "${EUID:-$(id -u)}" -eq 0 ] && "$@" || sudo "$@"; }

OS="$(uname -s)"

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

  ${BLD}Uninstaller — ${OS}${RST}
"

# ── Detect install locations ───────────────────────────────────────────────
SYSTEM_DIR="/opt/byteforge"
USER_DIR="$HOME/.byteforge"

if   [ -d "$SYSTEM_DIR" ]; then INSTALL_DIR="$SYSTEM_DIR"
elif [ -d "$USER_DIR"   ]; then INSTALL_DIR="$USER_DIR"
else
  warn "ByteForge install directory not found."
  warn "Checked: $SYSTEM_DIR and $USER_DIR"
  INSTALL_DIR=""
fi

# macOS: check for launchd plist
LAUNCHD_USER="$HOME/Library/LaunchAgents/com.byteforge.plist"
LAUNCHD_SYS="/Library/LaunchDaemons/com.byteforge.plist"

# ── Summary ────────────────────────────────────────────────────────────────
echo -e "  ${BLD}This will remove:${RST}"
[ -n "$INSTALL_DIR" ]                                         && echo -e "    ${ORG}•${RST} Files:    $INSTALL_DIR"
[ "$OS" = "Linux" ] && [ -f /etc/systemd/system/byteforge.service ] && echo -e "    ${ORG}•${RST} Service:  /etc/systemd/system/byteforge.service"
[ "$OS" = "Linux" ] && [ -d /etc/byteforge ]                          && echo -e "    ${ORG}•${RST} Secrets:  /etc/byteforge"
[ "$OS" = "Linux" ] && grep -q byteforge /etc/rc.local 2>/dev/null  && echo -e "    ${ORG}•${RST} rc.local: byteforge entry"
[ "$OS" = "Darwin" ] && [ -f "$LAUNCHD_USER" ]                      && echo -e "    ${ORG}•${RST} LaunchAgent: $LAUNCHD_USER"
[ "$OS" = "Darwin" ] && [ -f "$LAUNCHD_SYS"  ]                      && echo -e "    ${ORG}•${RST} LaunchDaemon: $LAUNCHD_SYS"
echo

# ── Confirm ────────────────────────────────────────────────────────────────
if [ -t 0 ]; then
  read -rp "  Are you sure you want to uninstall ByteForge? [y/N] " ans
  [[ "${ans:-n}" =~ ^[Yy] ]] || { echo -e "\n  Aborted.\n"; exit 0; }
fi
echo

# ── Linux: systemd ─────────────────────────────────────────────────────────
if [ "$OS" = "Linux" ] && command -v systemctl >/dev/null 2>&1; then
  if systemctl list-units --all --quiet byteforge.service 2>/dev/null | grep -q byteforge; then
    info "Stopping byteforge service..."
    run_p systemctl stop byteforge 2>/dev/null || true
    run_p systemctl disable byteforge 2>/dev/null || true
    ok "Service stopped and disabled."
  fi
  if [ -f /etc/systemd/system/byteforge.service ]; then
    run_p rm -f /etc/systemd/system/byteforge.service
    run_p systemctl daemon-reload
    ok "Service file removed."
  fi
fi

# ── Linux: rc.local fallback ───────────────────────────────────────────────
if [ "$OS" = "Linux" ] && grep -q byteforge /etc/rc.local 2>/dev/null; then
  info "Removing byteforge entry from /etc/rc.local..."
  run_p sed -i '/byteforge/d' /etc/rc.local
  ok "rc.local cleaned."
fi

# ── Linux: kill any running process ───────────────────────────────────────
if [ "$OS" = "Linux" ]; then
  pkill -f byteforge-server.py 2>/dev/null && ok "Running process killed." || true
fi

# ── macOS: launchd ─────────────────────────────────────────────────────────
if [ "$OS" = "Darwin" ]; then
  if [ -f "$LAUNCHD_USER" ]; then
    info "Unloading LaunchAgent..."
    launchctl unload "$LAUNCHD_USER" 2>/dev/null || true
    rm -f "$LAUNCHD_USER"
    ok "LaunchAgent removed."
  fi
  if [ -f "$LAUNCHD_SYS" ]; then
    info "Unloading LaunchDaemon..."
    run_p launchctl unload "$LAUNCHD_SYS" 2>/dev/null || true
    run_p rm -f "$LAUNCHD_SYS"
    ok "LaunchDaemon removed."
  fi
  pkill -f byteforge-server.py 2>/dev/null && ok "Running process killed." || true
fi

# ── Remove install directory ───────────────────────────────────────────────
if [ -n "$INSTALL_DIR" ] && [ -d "$INSTALL_DIR" ]; then
  info "Removing $INSTALL_DIR..."
  run_p rm -rf "$INSTALL_DIR"
  ok "Install directory removed."
fi

# ── Remove credentials directory ──────────────────────────────────────────
if [ -d /etc/byteforge ]; then
  run_p rm -rf /etc/byteforge
  ok "Credentials directory removed."
fi

# ── Done ───────────────────────────────────────────────────────────────────
echo -e "\n${ORG}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  ${GRN}${BLD}ByteForge has been uninstalled.${RST}"
echo -e "${ORG}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "  To reinstall: ${BLD}bash install.sh${RST}\n"
