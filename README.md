# ByteForge

ByteForge er en selvstændig homelab- og game-server platform med en mørk, teknisk æstetik: skarpe paneler, neon-orange highlights, mono labels og lav visuel støj.

Platformen kører direkte med den medfølgende Python-backend og bruger Docker som runtime til game servers og apps.

> **Built by Lucas Valentin og Kaspar Lythje** — NAS · RAID · MINECRAFT · DIT DATA · DIN KONTROL

---

## Features

### 🎮 Game Servers

Understøtter otte servertyper — alle styret via Docker:

- Minecraft Vanilla
- Minecraft Paper *(anbefalet — bedste performance)*
- Minecraft Spigot
- Minecraft Forge
- Minecraft Fabric
- FiveM *(kræver cfx.re-licens)*
- Terraria
- Custom game servers

Start, stop og restart pr. server med ét klik. CPU/RAM-grænser sættes individuelt.

### 🗄 NAS Storage

Del filer på tværs af alle enheder via NFS og Samba. Tilgå fra Windows, Mac og Linux med én central lagerplads på `/mnt/nas-share`.

### ⚡ RAID Beskyttelse

RAID 1 spejling via mdadm duplikerer data på to diske automatisk. Hvis én disk fejler, overlever data på den anden.

### 📁 Filhåndtering

Komplet filhåndtering direkte i browseren med fire storage-zoner:

| Zone | Adgang |
|------|--------|
| `public` | Tilgængeligt uden login via HTTP |
| `private` | Kun din profil |
| `shared` | Alle loggede brugere |
| `server data` | Per-game-server (worlds, mods, configs) |

Upload, slet, flyt, søg og opret mapper. Understøtter multi-upload.

### 👤 Multi-User Profiler

Tre adgangsniveauer:

- **Admin** — Fuld adgang inkl. brugeroprettelse og sletning
- **Bruger** — Start/stop servere og upload filer
- **Gæst** — Kun se status

### 🌐 Website Hosting

Host statiske hjemmesider fra `public` storage. Video, PDF og fildeling over HTTP.

### 🐳 Docker App Store

Installer apps med ét klik via presets:

- **Media Server** — Jellyfin
- **Cloud Storage** — Nextcloud
- **Password Manager** — Bitwarden
- **Ad Blocker** — Pi-hole
- **VPN** — WireGuard
- **Monitoring** — Grafana + Prometheus
- **Privacy Suite** — Bitwarden + Nextcloud + Pi-hole + WireGuard i ét klik

### 🤖 AI Assistant

Integreret Claude API (claude-sonnet-4-6). Stil spørgsmål om serveren, analysér logs og få performance-tips direkte i dashboardet.

---

## Installation

### Linux / macOS

```bash
unzip ByteForge.zip && cd ByteForge
sudo ./install.sh        # Linux
./install.sh             # macOS
```

### Windows

```powershell
.\install.ps1
```

Eller kør `install.bat` fra Explorer eller terminal — den kalder PowerShell-installeren.

Installeren spørger efter et ADMIN-password, kopierer filer, tilbyder Docker-installation og opsætter ByteForge som systemservice (systemd på Linux, launchd på macOS, Scheduled Task på Windows).

Åbn derefter:

```
http://127.0.0.1:8080
```

Log ind med `ADMIN` og det password du valgte.

---

## Manuel start

```bash
cd ByteForge
python3 byteforge-server.py
```

Første gang oprettes ADMIN-kontoen via login-skærmen, eller sæt password på forhånd:

```bash
BYTEFORGE_ADMIN_PASSWORD="vælg-et-stærkt-password" python3 byteforge-server.py
```

Skift port eller datamappe:

```bash
BYTEFORGE_HOME="/din/mappe" BYTEFORGE_PORT=9000 python3 byteforge-server.py
```

Data gemmes som standard i `~/.byteforge` (eller `/opt/byteforge` som root).

---

## Krav

- Python 3.8+
- Docker (kan installeres via terminal-installeren)
- Linux, macOS eller Windows

---

## Porte

| Service | Port | Protokol | Beskrivelse |
|---------|------|----------|-------------|
| ByteForge Panel | 8080 | TCP | Komplet kontrolpanel |
| Minecraft | 25565 | TCP/UDP | Game server (PaperMC) |
| NFS Server | 2049 | TCP | Network File System deling |
| Samba/SMB | 445 | TCP | Windows fildeling |
| WireGuard VPN | 51820 | UDP | VPN (installer via panel) |

---

## API

ByteForge eksponerer et REST API til scripting og integration:

| Metode | Endpoint | Beskrivelse |
|--------|----------|-------------|
| `GET` | `/api/all` | Samlet status for alle services |
| `GET` | `/api/game-servers` | Liste over game servers og status |
| `POST` | `/api/game-servers/create` | Opret en ny game server |
| `POST` | `/api/game-servers/action` | Start, stop eller genstart server |
| `GET` | `/api/files?scope=public` | List filer i storage-zone |
| `POST` | `/api/files/upload` | Upload fil til storage-zone |
| `POST` | `/api/files/action` | Flyt, slet eller omdøb fil |
| `GET` | `/api/users` | Brugerliste (kun admin) |
| `POST` | `/api/settings` | Opdater systemindstillinger |

```bash
# Hent alle servere
curl http://localhost:8080/api/game-servers

# Start en server
curl -X POST http://localhost:8080/api/game-servers/action \
  -H "Content-Type: application/json" \
  -d '{"id":"SERVER_ID","action":"start"}'
```

---

## NAS-tilslutning

```text
Windows:  \\10.194.177.172\nas-share
Mac:      nfs://10.194.177.172/mnt/nas-share
Linux:    mount -t nfs 10.194.177.172:/mnt/nas-share /mnt/remote
```

---

## Tech Stack

| Komponent | Detalje |
|-----------|---------|
| OS | Manjaro Linux (Arch-baseret, Kernel 6.x) |
| Container runtime | Docker v29.3.0 |
| NAS | NFS Server (`/mnt/nas-share`) |
| RAID | mdadm RAID 1 (`/mnt/raid`) |
| Minecraft | PaperMC via Docker (port 25565) |
| Backend | Python 3 (port 8080) |
| AI | Claude API (`claude-sonnet-4-6`) |
| Firewall | UFW |

---

---

## Licens

Built by Lucas Valentin — `github.com/ByteForgeAdmin/ByteForge`
