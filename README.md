# ByteForge

ByteForge er en selvstændig homelab- og game-server platform med samme mørke, tekniske stil som det oprindelige ByteForge/CasaOS theme: skarpe paneler, neon-orange highlights, mono labels og lav visuel støj.

Platformen er ikke afhængig af CasaOS. Den kan køres direkte med den medfølgende Python-backend og bruger Docker som simpel runtime til game servers.

## Core Features

- Administrer flere game servers:
  - Minecraft Vanilla
  - Minecraft Paper
  - Minecraft Spigot
  - Minecraft Forge
  - Minecraft Fabric
  - FiveM
  - Terraria
  - Custom game servers
- Start, stop og restart pr. server
- One-click server setup via Docker profiler
- CPU/RAM limits pr. game server
- Auto-restart metadata og Docker `unless-stopped`
- Filhåndtering:
  - upload
  - slet
  - flyt
  - søg
  - opret mapper
- Virtuelt storage layout:
  - public
  - private
  - shared
  - per-server data
- Multi-user profiler og adgangsmodel
- Website hosting område
- Video/PDF/fil-storage over public storage
- Mobilvenlig web app navigation
- Themes, sprog og custom background-indstillinger

## Kør Lokalt

```bash
cd ByteForge
python3 byteforge-server.py
```

Åbn derefter:

```text
http://localhost:8080
```

Første gang opretter ByteForge en `ADMIN` konto. Hvis du bruger installer-scriptet, bliver du bedt om at vælge ADMIN-adgangskoden under installationen:

```bash
sudo ./install.sh
```

På macOS bruges samme terminal-installer:

```bash
./install.sh
```

På Windows skal installeren køres fra PowerShell eller Windows Terminal:

```powershell
.\install.ps1
```

Alternativt kan `install.bat` startes fra terminal eller Explorer; den kalder PowerShell-installeren.

Hvis du starter manuelt, kan du enten vælge password i første login-skærm eller sætte det på forhånd:

```bash
BYTEFORGE_ADMIN_PASSWORD="vælg-et-stærkt-password" python3 byteforge-server.py
```

Som standard gemmes data i `~/.byteforge` for almindelige brugere og `/opt/byteforge` når serveren køres som root.

```text
~/.byteforge
```

Det kan ændres uden kodeændringer:

```bash
BYTEFORGE_HOME="$HOME/.byteforge" BYTEFORGE_PORT=8080 python3 byteforge-server.py
```

## API

- `GET /api/all`
- `GET /api/game-servers`
- `POST /api/game-servers/create`
- `POST /api/game-servers/action`
- `GET /api/files?scope=public`
- `POST /api/files/upload`
- `POST /api/files/action`
- `GET /api/users`
- `POST /api/settings`

## Legacy Theme

`ByteForge/byteforge-custom.css` og `ByteForge/byteforge-deploy.sh` er stadig med, hvis du vil bruge den gamle CasaOS theme-del. Selve platformen i `byteforge-platform.html` og `byteforge-server.py` er CasaOS-uafhængig.
