# ByteForge — Codex/AI Assistant Context Prompt

Paste this at the start of any AI chat session to give full context about the project.

---

## What is ByteForge?

ByteForge is an all-in-one homelab server management platform — the goal is to beat CasaOS.
It runs as a **single Python file backend** + **single HTML file frontend** with zero install dependencies.
It works on **Windows, macOS, and Linux** (Ubuntu, Arch, Fedora, etc.).

The owner (Admin) wants ByteForge to eventually combine the best of:
- **Proxmox** (VM/container management)
- **CasaOS** (app store, Docker UI)
- **Nextcloud** (file storage)
- **With its own AI assistant built in**

---

## Architecture

| Layer | Technology |
|---|---|
| Backend | Python 3 `http.server.HTTPServer` — one file: `ByteForge/byteforge-server.py` |
| Frontend | Vanilla JS single-page app — one file: `ByteForge/byteforge-platform.html` |
| Runtime | Docker (via `subprocess` calls) for all game servers and apps |
| Config | JSON file at `$BYTEFORGE_HOME/servers.json` |
| No frameworks | No Flask, no React, no npm — pure stdlib Python + vanilla JS |

The backend serves the HTML at `/` and exposes a REST JSON API at `/api/*`.
The frontend is a single-page app with sidebar navigation — no page reloads.

---

## File Structure

```
ByteForge/
├── ByteForge/
│   ├── byteforge-server.py      # Python backend (~1300 lines)
│   ├── byteforge-platform.html  # Frontend SPA (~2000 lines)
│   └── minecraft-server/        # MC docker-compose + start/stop scripts
├── install.sh                   # Linux/macOS one-command installer
├── install.ps1                  # Windows PowerShell installer
├── install.bat                  # Windows batch double-click installer
└── CODEX_PROMPT.md             # This file
```

---

## Backend — Key Globals & Functions

```python
PLATFORM = platform.system()  # 'Linux', 'Darwin', 'Windows'
BASE_DIR  # Data directory (/opt/byteforge or ~/.byteforge)
CONFIG_PATH  # servers.json path
SERVER_TYPES  # Dict of 24 game server templates (minecraft, ARK, Rust, Valheim, CS2, etc.)
APP_CATALOG   # Dict of 40+ installable apps (Jellyfin, Gitea, Grafana, Nextcloud, etc.)
PRIVACY_APPS  # Dict of privacy apps (Bitwarden, Pi-hole, WireGuard, etc.)
_METRICS_HISTORY  # List of last 60 CPU/RAM readings (5s intervals, background thread)
```

Key functions:
- `get_system()` — CPU%, RAM, temp, uptime (cross-platform)
- `get_hardware()` — CPU model, GPU, motherboard, hostname
- `get_disks()` — disk usage per mount point
- `get_game_servers()` — all configured servers with live Docker status
- `game_action(id, action)` — start/stop/restart a game server container
- `create_game_server(body)` — create + deploy a new game server
- `appstore_install(app_id)` / `appstore_uninstall(app_id)` — one-click app management
- `exec_command(cmd)` — safe shell execution for web terminal (has blocklist)
- `deploy_app(app_id)` — deploy a privacy app
- `install_docker_system()` — auto-install Docker for current OS/distro
- `install_service_system()` — install ByteForge as systemd/launchd/Task Scheduler service

---

## API Routes

### GET
| Route | Returns |
|---|---|
| `/` | Serves `byteforge-platform.html` |
| `/api/all` | system + hardware + disks + raid + nas + minecraft + docker + game_servers |
| `/api/system` | CPU, RAM, temp, uptime |
| `/api/hardware` | CPU model, GPU, motherboard, hostname, platform |
| `/api/disks` | Disk usage per mount |
| `/api/docker` | Running Docker containers |
| `/api/game-servers` | All game server profiles + live status + SERVER_TYPES |
| `/api/metrics/history` | Last 60 CPU/RAM data points (for graphs) |
| `/api/appstore` | All 40+ apps with install status |
| `/api/setup` | Docker installed?, service installed?, port, base_dir |
| `/api/users` | Users list + settings (theme, language, background) |
| `/api/background` | Serves uploaded background image |

### POST
| Route | Body | Action |
|---|---|---|
| `/api/game-servers/create` | `{name, type, cpu_limit, memory_limit}` | Create + deploy game server |
| `/api/game-servers/action` | `{id, action}` | start/stop/restart game server |
| `/api/appstore/install` | `{app}` | Install app from APP_CATALOG |
| `/api/appstore/uninstall` | `{app}` | Remove app container |
| `/api/docker/action` | `{container, action}` | start/stop/restart/remove any container |
| `/api/apps/deploy` | `{app}` | Deploy a PRIVACY_APPS app |
| `/api/terminal/exec` | `{cmd}` | Execute shell command (with safety blocklist) |
| `/api/settings` | `{theme, language, background}` | Save user settings |
| `/api/setup/docker` | `{}` | Install Docker for current OS |
| `/api/setup/service` | `{}` | Install ByteForge as system service |
| `/api/nas/action` | `{action}` | restart NFS server |
| `/api/background/upload` | multipart image | Upload + set background image |
| `/api/files/upload` | multipart file | Upload file to storage |
| `/api/files/action` | `{action, scope, path}` | mkdir/delete/move/search |

---

## Frontend — Key JS Functions

```js
nav(id, el)           // Switch page, calls loadPage()
loadOverview()        // Dashboard stats + disk overview
loadSystem()          // CPU/RAM rings + detail
loadDocker()          // Container table + Docker install banner
loadGameServers()     // Game server cards with cover images
loadAppStore()        // App store with search + category filter
filterApps(cat)       // Filter app store by category or search term
appInstall(id)        // Install app from store
appUninstall(id)      // Remove app
initTerminal()        // Web terminal init
quickCmd(cmd)         // Run a preset command in terminal
handleTermKey(e)      // Terminal keyboard handler (Enter = exec, ↑↓ = history)
updateGraphs()        // Fetch metrics history, draw canvas graphs
checkNotifications()  // Check CPU/RAM thresholds, update bell badge
applyBackground(bg)   // Apply background: 'grid'|'none'|'forge'|'matrix'|'nebula'|URL
applyTheme(theme)     // Apply theme: 'forge-dark'|'forge-light'|'high-contrast'
applyLanguage(lang)   // Apply i18n: 'da'|'en' (uses data-i18n attributes)
setBgPreset(preset)   // Click a bg preset tile
loadSettings()        // Load + apply theme/language/background from saved settings
saveSettings()        // Save settings to backend
gameAction(id, action)// Start/stop/restart a game server
createGameServer()    // Read form + POST to create a new server
updateCoverPreview()  // Show game cover image when type changes in dropdown
```

---

## Current Features (what's already built)

### Core
- ✅ Web dashboard with real-time CPU/RAM/temp/uptime ticker
- ✅ Real-time canvas graphs (CPU + RAM, 5-minute rolling history)
- ✅ Cross-platform (Windows / macOS / Linux Ubuntu/Arch/Fedora)
- ✅ Notification bell (CPU/RAM threshold alerts)
- ✅ Language switching: Danish / English (data-i18n system)
- ✅ 3 themes: Forge Dark, Forge Light, High Contrast
- ✅ Custom background: 5 presets + URL + image upload

### App Management
- ✅ App Store with 40+ apps, search, 11 categories, one-click install/uninstall
- ✅ Docker container management (start/stop/restart/remove)
- ✅ Docker install button (auto-detects distro: apt/pacman/dnf/brew)
- ✅ Game Servers: 24 types with Steam CDN cover art, one-click create
- ✅ Privacy Suite: Bitwarden, Nextcloud, Pi-hole, WireGuard

### Storage & System
- ✅ Disk usage overview with progress bars
- ✅ NAS/NFS management
- ✅ RAID monitoring (/proc/mdstat)
- ✅ Hardware info (CPU model, GPU, motherboard)
- ✅ File manager (upload/download/delete/mkdir/search)
- ✅ Multi-user + roles system

### Developer
- ✅ Web Terminal (command runner with history, quick-command buttons)
- ✅ AI Assistant (Claude API via browser)
- ✅ JSON formatter, API tester, log viewer
- ✅ One-command install scripts (install.sh / install.ps1 / install.bat)
- ✅ Runs as system service (systemd / launchd / Task Scheduler)

---

## What Needs to be Built (Roadmap)

### High priority (to beat CasaOS)
- 🔲 Reverse proxy UI (Nginx Proxy Manager integration or built-in routing)
- 🔲 Automatic SSL certificates (Let's Encrypt / Caddy)
- 🔲 Login system with 2FA (currently no auth)
- 🔲 More app store apps (target 100+)

### Medium priority
- 🔲 Network graphs (bandwidth in/out over time)
- 🔲 Cron job scheduler UI
- 🔲 Discord/email alert webhooks
- 🔲 Backup scheduler (local + cloud)
- 🔲 Container logs viewer per app
- 🔲 VM support (via QEMU/libvirt)

### Unique ByteForge features (differentiation)
- 🔲 Achievement system
- 🔲 Custom startup animation / boot screen
- 🔲 Plugin system
- 🔲 Live collaboration (multiple users editing config at once)
- 🔲 One-click deploy websites with SSL

---

## Code Style Rules

- **No frameworks** — pure Python stdlib + vanilla JS, no npm, no pip installs
- **No comments** on obvious code — only add comments for non-obvious WHY
- **Cross-platform first** — always check `PLATFORM` before using Linux-specific commands
- **Escape all HTML** — use `escapeHTML()` in JS for any user/server data rendered to DOM
- **No magic numbers** — use named constants or inline with obvious context
- **Fail gracefully** — all API calls wrapped in try/except, all JS fetches in try/catch
- **Single file constraint** — keep everything in the two main files unless absolutely necessary

---

## Running the Server

```bash
# Linux/macOS
sudo python3 ByteForge/byteforge-server.py

# Windows
python ByteForge\byteforge-server.py

# With custom port
BYTEFORGE_PORT=9090 python3 ByteForge/byteforge-server.py

# Then open: http://localhost:8080
```

---

## Key Design Decisions

1. **Single Python file** — easy to deploy anywhere, no virtualenv needed
2. **Docker for everything** — game servers, apps, privacy tools all run in containers
3. **JSON config** — `servers.json` is the only state file, easy to back up
4. **No database** — simplicity over scalability for a homelab tool
5. **Vanilla JS** — loads instantly, no build step, works offline
6. **Port 8080** — avoids needing root just to bind to port 80
