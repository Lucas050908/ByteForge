#!/usr/bin/env bash
# ByteForge — Linux starter
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/ByteForge"
LOG_FILE="$ROOT_DIR/byteforge.log"
PORT="${BYTEFORGE_PORT:-8080}"

# ── Farver ────────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
  ORG='\033[38;5;208m' GRN='\033[0;32m' YLW='\033[1;33m'
  RED='\033[0;31m' BLD='\033[1m' RST='\033[0m'
else
  ORG='' GRN='' YLW='' RED='' BLD='' RST=''
fi

ok()   { echo -e "  ${GRN}✓${RST}  $*"; }
warn() { echo -e "  ${YLW}!${RST}  $*"; }
die()  { echo -e "\n${RED}[FEJL]${RST} $*\n" >&2; exit 1; }
info() { echo -e "  ${ORG}→${RST}  $*"; }

echo -e "
${ORG}  BYTEFORGE SERVER${RST}
  ════════════════
"

# ── Stop-argument: ./start.sh stop ───────────────────────────────────────────
if [ "${1:-}" = "stop" ]; then
  PID="$(ss -tlnp "sport = :$PORT" 2>/dev/null | awk 'NR>1 {match($0, /pid=([0-9]+)/, a); if (a[1]) print a[1]}' | head -1)"
  if [ -z "$PID" ]; then
    PID="$(lsof -ti ":$PORT" 2>/dev/null | head -1 || true)"
  fi
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null && ok "Server stoppet (PID $PID)." || die "Kunne ikke stoppe PID $PID."
  else
    warn "Ingen server fundet på port $PORT."
  fi
  exit 0
fi

# ── 1. Tjek kildefiler ────────────────────────────────────────────────────────
[ -f "$SRC_DIR/byteforge-server.py" ] || die "ByteForge kildefiler ikke fundet i $SRC_DIR"

# ── 2. Find Python 3.8+ ──────────────────────────────────────────────────────
PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver="$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
    major="${ver%%.*}"
    minor="${ver##*.}"
    if [ -n "$ver" ] && [ "$major" -ge 3 ] && [ "$minor" -ge 8 ] 2>/dev/null; then
      PYTHON_BIN="$candidate"
      ok "Python $ver fundet ($candidate)"
      break
    elif [ -n "$ver" ]; then
      warn "Python $ver er for gammel (kræver 3.8+) — prøver næste..."
    fi
  fi
done
[ -n "$PYTHON_BIN" ] || die "Python 3.8+ ikke fundet.\nInstaller med: sudo apt install python3  (eller dnf/pacman/zypper)"

# ── Browser-hjælper ──────────────────────────────────────────────────────────
_open_browser() {
  local url="$1"
  if command -v xdg-open   >/dev/null 2>&1; then xdg-open   "$url" &
  elif command -v gnome-open >/dev/null 2>&1; then gnome-open "$url" &
  elif command -v kde-open   >/dev/null 2>&1; then kde-open   "$url" &
  fi
}

# ── 3. Tjek om port allerede er i brug ───────────────────────────────────────
if ss -tlnH "sport = :$PORT" 2>/dev/null | grep -q ":$PORT" || \
   { command -v lsof >/dev/null 2>&1 && lsof -ti ":$PORT" >/dev/null 2>&1; }; then
  warn "Port $PORT er allerede i brug — ByteForge kører muligvis allerede."
  info "Åbner http://127.0.0.1:$PORT ..."
  _open_browser "http://127.0.0.1:$PORT"
  exit 0
fi

# ── 4. Vis IP-adresser ────────────────────────────────────────────────────────
LAN_IP="$(ip -4 addr show 2>/dev/null | awk '/inet / && !/127\./ {print $2}' | cut -d/ -f1 | head -1 || \
          hostname -I 2>/dev/null | awk '{print $1}' || true)"

info "Lokal:     http://127.0.0.1:$PORT"
[ -n "$LAN_IP" ] && info "Netværk:   http://$LAN_IP:$PORT"
info "Log:       $LOG_FILE"
echo

# ── 5. Åbn browser når port svarer (baggrundstråd) ───────────────────────────
(
  for _ in $(seq 1 15); do
    sleep 1
    if bash -c "echo >/dev/tcp/127.0.0.1/$PORT" 2>/dev/null; then
      _open_browser "http://127.0.0.1:$PORT"
      break
    fi
  done
) &
BROWSER_PID=$!

# ── 6. Start server med auto-restart og log til fil ──────────────────────────
info "Starter server... (CTRL+C for at stoppe)"
echo
trap 'echo -e "\n  Server stoppet."; kill $BROWSER_PID 2>/dev/null; exit 0' INT TERM

cd "$SRC_DIR"
while true; do
  $PYTHON_BIN byteforge-server.py >> "$LOG_FILE" 2>&1
  echo -e "  ${YLW}[!]${RST} Server stoppede uventet — genstarter om 3 sekunder... (CTRL+C for at afbryde)"
  sleep 3
done
