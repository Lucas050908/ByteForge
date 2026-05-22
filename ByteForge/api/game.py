from pathlib import Path

from api.config import SERVER_ROOT, load_config, save_config
from api.utils import run, slugify, docker_available, docker_status, docker_stats, docker_logs, container_exists

_STEAM = "https://cdn.cloudflare.steamstatic.com/steam/apps/{}/header.jpg"

SERVER_TYPES = {
    "minecraft-vanilla": {
        "name": "Minecraft Vanilla",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "VANILLA"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-paper": {
        "name": "Minecraft Paper",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "PAPER"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-spigot": {
        "name": "Minecraft Spigot",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "SPIGOT"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-forge": {
        "name": "Minecraft Forge",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "FORGE"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "minecraft-fabric": {
        "name": "Minecraft Fabric",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "FABRIC"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover.png",
        "category": "Minecraft",
    },
    "fivem": {
        "name": "FiveM",
        "image": "spritsail/fivem",
        "env": {},
        "ports": ["30120:30120/tcp", "30120:30120/udp"],
        "data": "/config",
        "cover": _STEAM.format(271590),
        "category": "Andre",
    },
    "terraria": {
        "name": "Terraria",
        "image": "ryshe/terraria",
        "env": {"WORLD_FILENAME": "byteforge.wld"},
        "ports": ["7777:7777"],
        "data": "/root/.local/share/Terraria/Worlds",
        "cover": _STEAM.format(105600),
        "category": "Andre",
    },
    # ── Survival / Open World ──
    "ark-survival-evolved": {
        "name": "ARK Survival Evolved",
        "image": "azixmcaze/ark-se-server",
        "env": {"SESSIONNAME": "ByteForge ARK", "SERVERMAP": "TheIsland", "ADMINPASSWORD": "byteforge", "MAXPLAYERS": "20", "SERVERPASSWORD": ""},
        "ports": ["7777:7777/udp", "7778:7778/udp", "27015:27015/udp"],
        "data": "/server",
        "cover": _STEAM.format(346110),
        "category": "Survival / Open World",
    },
    "palworld": {
        "name": "Palworld",
        "image": "thijsvanloef/palworld-server-docker",
        "env": {"PLAYERS": "16", "MULTITHREADING": "true", "COMMUNITY": "false", "SERVER_NAME": "ByteForge Palworld", "ADMIN_PASSWORD": "byteforge", "SERVER_PASSWORD": ""},
        "ports": ["8211:8211/udp", "27015:27015/udp"],
        "data": "/palworld",
        "cover": _STEAM.format(1623730),
        "category": "Survival / Open World",
    },
    "rust": {
        "name": "Rust",
        "image": "didstopia/rust-server",
        "env": {"RUST_SERVER_STARTUP_ARGUMENTS": "+server.maxplayers 50 +server.hostname \"ByteForge Rust\"", "TZ": "Europe/Copenhagen"},
        "ports": ["28015:28015/udp", "28016:28016"],
        "data": "/steamcmd/rust",
        "cover": _STEAM.format(252490),
        "category": "Survival / Open World",
    },
    "7-days-to-die": {
        "name": "7 Days to Die",
        "image": "vinanrra/7dtd-server",
        "env": {"START_MODE": "1", "VERSION": "stable", "TZ": "Europe/Copenhagen"},
        "ports": ["26900:26900", "26900:26900/udp", "26901:26901/udp", "26902:26902/udp"],
        "data": "/home/sdtdserver",
        "cover": _STEAM.format(251570),
        "category": "Survival / Open World",
    },
    "dayz": {
        "name": "DayZ",
        "image": "drpain/dayz-server",
        "env": {"SERVER_NAME": "ByteForge DayZ", "MAX_PLAYERS": "20"},
        "ports": ["2302:2302/udp", "2303:2303/udp", "2304:2304/udp"],
        "data": "/dayzsrv",
        "cover": _STEAM.format(221100),
        "category": "Survival / Open World",
    },
    "valheim": {
        "name": "Valheim",
        "image": "lloesche/valheim-server",
        "env": {"SERVER_NAME": "ByteForge Valheim", "WORLD_NAME": "Dedicated", "SERVER_PASS": "byteforge", "SERVER_PUBLIC": "1"},
        "ports": ["2456:2456/udp", "2457:2457/udp", "2458:2458/udp"],
        "data": "/config",
        "cover": _STEAM.format(892970),
        "category": "Survival / Open World",
    },
    "project-zomboid": {
        "name": "Project Zomboid",
        "image": "danixu86/project-zomboid-server",
        "env": {"ADMINPASSWORD": "byteforge"},
        "ports": ["16261:16261/udp", "16262:16262/udp"],
        "data": "/data",
        "cover": _STEAM.format(108600),
        "category": "Survival / Open World",
    },
    "v-rising": {
        "name": "V Rising",
        "image": "trueosiris/vrising",
        "env": {"SERVERNAME": "ByteForge V Rising"},
        "ports": ["9876:9876/udp", "9877:9877/udp"],
        "data": "/mnt/vrising-data",
        "cover": _STEAM.format(1604030),
        "category": "Survival / Open World",
    },
    "sons-of-the-forest": {
        "name": "Sons of the Forest",
        "image": "jammsen/sons-of-the-forest",
        "env": {"SERVER_NAME": "ByteForge SotF", "SERVER_PASSWORD": "byteforge", "MAX_PLAYERS": "8"},
        "ports": ["8766:8766/udp", "27016:27016/udp", "9700:9700/udp"],
        "data": "/sonsoftheforest",
        "cover": _STEAM.format(1326470),
        "category": "Survival / Open World",
    },
    # ── Shooter / Action ──
    "counter-strike-2": {
        "name": "Counter-Strike 2",
        "image": "cm2network/cs2",
        "env": {"CS2_SERVERNAME": "ByteForge CS2", "CS2_CHEATS": "0", "CS2_PORT": "27015"},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/cs2-dedicated",
        "cover": _STEAM.format(730),
        "category": "Shooter / Action",
    },
    "team-fortress-2": {
        "name": "Team Fortress 2",
        "image": "cm2network/tf2",
        "env": {"SRCDS_TOKEN": ""},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/tf-dedicated",
        "cover": _STEAM.format(440),
        "category": "Shooter / Action",
    },
    "left4dead2": {
        "name": "Left 4 Dead 2",
        "image": "cm2network/l4d2",
        "env": {},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/l4d2-dedicated",
        "cover": _STEAM.format(550),
        "category": "Shooter / Action",
    },
    "gmod": {
        "name": "Garry's Mod",
        "image": "cm2network/garrysmod",
        "env": {"SRCDS_TOKEN": ""},
        "ports": ["27015:27015/udp", "27015:27015"],
        "data": "/home/steam/gmod-dedicated",
        "cover": _STEAM.format(4000),
        "category": "Shooter / Action",
    },
    # ── Simulation / Builder ──
    "satisfactory": {
        "name": "Satisfactory",
        "image": "wolveix/satisfactory-server",
        "env": {"MAXPLAYERS": "4", "AUTOPAUSE": "true", "AUTOSAVENUM": "3"},
        "ports": ["7777:7777/udp"],
        "data": "/config",
        "cover": _STEAM.format(526870),
        "category": "Simulation / Builder",
    },
    "factorio": {
        "name": "Factorio",
        "image": "factoriotools/factorio",
        "env": {},
        "ports": ["34197:34197/udp", "27015:27015"],
        "data": "/factorio",
        "cover": _STEAM.format(427520),
        "category": "Simulation / Builder",
    },
    "astroneer": {
        "name": "Astroneer",
        "image": "phntxx/astroneer",
        "env": {},
        "ports": ["8777:8777/udp", "7777:7777/udp"],
        "data": "/data",
        "cover": _STEAM.format(361420),
        "category": "Simulation / Builder",
    },
    "space-engineers": {
        "name": "Space Engineers",
        "image": "mmmaxwwwell/space-engineers-server",
        "env": {"SERVER_NAME": "ByteForge Space Engineers"},
        "ports": ["27016:27016/udp"],
        "data": "/config",
        "cover": _STEAM.format(244850),
        "category": "Simulation / Builder",
    },
    "farming-simulator-22": {
        "name": "Farming Simulator 22",
        "image": "lysander07/farming-simulator-22",
        "env": {},
        "ports": ["10823:10823"],
        "data": "/farmingsimulator22/game",
        "cover": _STEAM.format(1300530),
        "category": "Simulation / Builder",
    },
    "farming-simulator-25": {
        "name": "Farming Simulator 25",
        "image": "lysander07/farming-simulator-25",
        "env": {},
        "ports": ["10823:10823"],
        "data": "/farmingsimulator25/game",
        "cover": _STEAM.format(2300260),
        "category": "Simulation / Builder",
    },
    # ── Other ──
    "unturned": {
        "name": "Unturned",
        "image": "gameservermanagers/gameservermanager",
        "env": {"LGSM_GAMESERVER": "untserver"},
        "ports": ["27015:27015/udp", "27016:27016/udp"],
        "data": "/data/serverfiles",
        "cover": _STEAM.format(304930),
        "category": "Andre",
    },
    "euro-truck-simulator-2": {
        "name": "Euro Truck Simulator 2",
        "image": "brendanmanning/ets2-server",
        "env": {},
        "ports": ["27015:27015/udp"],
        "data": "/data",
        "cover": _STEAM.format(227300),
        "category": "Andre",
    },
    "minecraft-bedrock": {
        "name": "Minecraft Bedrock",
        "image": "itzg/minecraft-bedrock-server",
        "env": {"EULA": "TRUE"},
        "ports": ["19132:19132/udp"],
        "data": "/data",
        "cover": "https://www.minecraft.net/content/dam/games/minecraft/key-art/MC_Vanilla_Updatesart_Homepage-Subnav_816x232.jpg",
        "category": "Minecraft",
    },
    "dont-starve-together": {
        "name": "Don't Starve Together",
        "image": "mathielo/dont-starve-together",
        "env": {},
        "ports": ["10999:10999/udp","10998:10998/udp"],
        "data": "/home/steam/.klei",
        "cover": _STEAM.format(322330),
        "category": "Survival / Open World",
    },
    "barotrauma": {
        "name": "Barotrauma",
        "image": "ich777/steamcmd:barotrauma",
        "env": {"GAME_ID": "1026340"},
        "ports": ["27015:27015/udp"],
        "data": "/serverdata",
        "cover": _STEAM.format(1026340),
        "category": "Survival / Open World",
    },
    "conan-exiles": {
        "name": "Conan Exiles",
        "image": "ich777/steamcmd:conanexiles",
        "env": {"GAME_ID": "443030"},
        "ports": ["7777:7777/udp","7778:7778/udp","27015:27015/udp"],
        "data": "/serverdata",
        "cover": _STEAM.format(440900),
        "category": "Survival / Open World",
    },
    "arma-reforger": {
        "name": "Arma Reforger",
        "image": "ich777/steamcmd:armareforger",
        "env": {"GAME_ID": "1874900"},
        "ports": ["2001:2001/udp","17777:17777/udp"],
        "data": "/serverdata",
        "cover": _STEAM.format(1874900),
        "category": "Shooter / Action",
    },
    "insurgency-sandstorm": {
        "name": "Insurgency: Sandstorm",
        "image": "ich777/steamcmd:insurgencysandstorm",
        "env": {"GAME_ID": "581330"},
        "ports": ["27102:27102/udp","27131:27131/udp"],
        "data": "/serverdata",
        "cover": _STEAM.format(581320),
        "category": "Shooter / Action",
    },
    "minecraft-purpur": {
        "name": "Minecraft Purpur",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "PURPUR"},
        "ports": ["25565:25565"],
        "data": "/data",
        "cover": "https://www.minecraft.net/content/dam/games/minecraft/key-art/MC_Vanilla_Updatesart_Homepage-Subnav_816x232.jpg",
        "category": "Minecraft",
    },
    "stardew-valley": {
        "name": "Stardew Valley",
        "image": "lloesche/stardew-valley-server",
        "env": {},
        "ports": ["24642:24642/udp"],
        "data": "/config",
        "cover": _STEAM.format(413150),
        "category": "Simulation / Builder",
    },
    "custom": {
        "name": "Custom Game Server",
        "image": "ubuntu:latest",
        "env": {},
        "ports": [],
        "data": "/data",
        "cover": "",
        "category": "Andre",
    },
}


def get_game_servers(include_logs=False):
    config = load_config()
    servers = []
    for server in config["servers"]:
        item = dict(server)
        item["kind"] = SERVER_TYPES.get(item.get("type"), SERVER_TYPES["custom"])["name"]
        item["status"] = docker_status(item["container"])
        item["stats"] = docker_stats(item["container"]) if item["status"] == "running" else {"cpu": "-", "memory": "-", "network": "-"}
        item["logs"] = docker_logs(item["container"]) if include_logs else ""
        item["path"] = str(Path(item.get("path", SERVER_ROOT / item["id"])))
        servers.append(item)
    return servers


def legacy_minecraft():
    servers = get_game_servers(include_logs=True)
    mc = next((s for s in servers if s["type"].startswith("minecraft")), None)
    if not mc:
        return {"status": "stopped", "logs": "", "players": "", "port": 25565}
    players = ""
    if mc["status"] == "running":
        out, _, _ = run(["docker", "exec", mc["container"], "rcon-cli", "list"], timeout=5, shell=False)
        players = out
    return {"status": mc["status"], "logs": mc["logs"], "players": players, "port": mc.get("port", 25565)}


def _docker_run_server(server):
    profile = SERVER_TYPES.get(server.get("type"), SERVER_TYPES["custom"])
    data_path = Path(server.get("path", str(SERVER_ROOT / server["id"])))
    data_path.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "-d", "--name", server["container"], "--label", "byteforge.server=true"]
    cmd += ["--cpus", str(server.get("cpu_limit", "2")), "--memory", str(server.get("memory_limit", "2g"))]
    if server.get("auto_restart", True):
        cmd += ["--restart", "unless-stopped"]
    for key, value in profile["env"].items():
        cmd += ["-e", f"{key}={value}"]
    port = server.get("port", 0)
    for mapping in profile["ports"]:
        host, rest = mapping.split(":", 1)
        if port and host.isdigit():
            mapping = f"{port}:{rest}"
        cmd += ["-p", mapping]
    cmd += ["-v", f"{data_path}:{profile['data']}", profile["image"]]
    out, err, code = run(cmd, timeout=300, shell=False)
    return {"ok": code == 0, "msg": out or err or f"{server['name']} startet"}


def game_action(server_id, action):
    server = next((s for s in load_config()["servers"] if s["id"] == server_id), None)
    if not server:
        return {"ok": False, "msg": "Server ikke fundet"}
    if action not in ("start", "stop", "restart"):
        return {"ok": False, "msg": "Ukendt kommando"}
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig"}
    if action in ("start", "restart") and not container_exists(server["container"]):
        return _docker_run_server(server)
    out, err, code = run(["docker", action, server["container"]], timeout=60, shell=False)
    return {"ok": code == 0, "msg": out or err or f"{server['name']} {action}"}


def create_game_server(body):
    config = load_config()
    name = body.get("name") or "ByteForge Server"
    server_type = body.get("type") or "minecraft-paper"
    profile = SERVER_TYPES.get(server_type, SERVER_TYPES["custom"])
    sid = slugify(name)
    existing_ids = {s["id"] for s in config["servers"]}
    base_sid = sid
    index = 2
    while sid in existing_ids:
        sid = f"{base_sid}-{index}"
        index += 1

    raw_port = body.get("port") or (profile["ports"][0].split(":", 1)[0].split("/", 1)[0] if profile["ports"] else "0")
    try:
        port = int(str(raw_port).strip()) if str(raw_port).strip() not in ("", "0") else 0
        if port < 1 or port > 65535:
            port = 0
    except (ValueError, TypeError):
        port = 0
    # Auto-increment port if already in use by another server
    used_ports = {s.get("port") for s in config["servers"]}
    while port and port in used_ports:
        port += 1
    container = f"byteforge-{sid}"
    data_path = SERVER_ROOT / sid
    data_path.mkdir(parents=True, exist_ok=True)

    server = {
        "id": sid,
        "name": name,
        "type": server_type,
        "container": container,
        "port": port,
        "cpu_limit": str(body.get("cpu_limit") or "2"),
        "memory_limit": str(body.get("memory_limit") or "2g"),
        "auto_restart": bool(body.get("auto_restart", True)),
        "owner": body.get("owner") or "admin",
        "visibility": body.get("visibility") or "shared",
        "path": str(data_path),
    }
    config["servers"].append(server)
    save_config(config)

    if not body.get("deploy", True):
        return {"ok": True, "server": server, "msg": "Serverprofil oprettet uden deploy"}
    if not docker_available():
        return {"ok": False, "server": server, "msg": "Docker er ikke tilgængelig. Profilen er gemt."}

    cmd = ["docker", "run", "-d", "--name", container, "--label", "byteforge.server=true"]
    cmd += ["--cpus", server["cpu_limit"], "--memory", server["memory_limit"]]
    if server["auto_restart"]:
        cmd += ["--restart", "unless-stopped"]
    for key, value in profile["env"].items():
        cmd += ["-e", f"{key}={value}"]
    for mapping in profile["ports"]:
        host, rest = mapping.split(":", 1)
        if port and host.isdigit():
            mapping = f"{port}:{rest}"
        cmd += ["-p", mapping]
    cmd += ["-v", f"{data_path}:{profile['data']}", profile["image"]]

    out, err, code = run(cmd, timeout=300, shell=False)
    return {"ok": code == 0, "server": server, "msg": out or err or "Server oprettet"}


def delete_game_server(server_id):
    config = load_config()
    server = next((s for s in config["servers"] if s["id"] == server_id), None)
    if not server:
        return {"ok": False, "msg": "Server ikke fundet"}
    if docker_available() and container_exists(server["container"]):
        run(["docker", "rm", "-f", server["container"]], timeout=15, shell=False)
    config["servers"] = [s for s in config["servers"] if s["id"] != server_id]
    save_config(config)
    return {"ok": True, "msg": f"{server['name']} slettet"}


# ── MODS & PLUGINS ──

def _mods_dir(server_id):
    config = load_config()
    server = next((s for s in config.get("servers", []) if s["id"] == server_id), None)
    if not server:
        return None, None
    profile = SERVER_TYPES.get(server.get("type"), SERVER_TYPES["custom"])
    data_path = Path(server.get("path") or (SERVER_ROOT / server_id))
    # Minecraft Paper/Spigot/Forge use plugins or mods folder
    kind = f"{server.get('type', '')} {profile.get('name', '')}".lower()
    if any(name in kind for name in ("paper", "spigot", "purpur")):
        mods_path = data_path / "plugins"
    elif any(name in kind for name in ("forge", "fabric")):
        mods_path = data_path / "mods"
    else:
        mods_path = data_path / "mods"
    return server, mods_path

def list_server_mods(server_id):
    server, mods_path = _mods_dir(server_id)
    if not server:
        return {"ok": False, "msg": "Server ikke fundet", "mods": []}
    if not mods_path or not mods_path.exists():
        return {"ok": True, "mods": []}
    mods = [f.name for f in mods_path.iterdir() if f.suffix in (".jar", ".zip", ".dll", ".so") and f.is_file()]
    return {"ok": True, "mods": sorted(mods)}

def install_server_mod(server_id, url=None, modrinth_slug=None):
    import urllib.request as urlreq
    server, mods_path = _mods_dir(server_id)
    if not server:
        return {"ok": False, "msg": "Server ikke fundet"}
    mods_path.mkdir(parents=True, exist_ok=True)
    if modrinth_slug:
        try:
            with urlreq.urlopen(f"https://api.modrinth.com/v2/project/{modrinth_slug}/version?loaders=[\"fabric\",\"forge\",\"paper\",\"spigot\"]&limit=1", timeout=8) as r:
                versions = __import__("json").loads(r.read())
            if not versions:
                with urlreq.urlopen(f"https://api.modrinth.com/v2/project/{modrinth_slug}/version?limit=1", timeout=8) as r:
                    versions = __import__("json").loads(r.read())
            if not versions:
                return {"ok": False, "msg": "Ingen kompatibel version fundet på Modrinth"}
            file_info = versions[0]["files"][0]
            url = file_info["url"]
            filename = file_info["filename"]
        except Exception as e:
            return {"ok": False, "msg": f"Modrinth fejl: {e}"}
    else:
        if not url:
            return {"ok": False, "msg": "Ingen URL angivet"}
        filename = url.split("/")[-1].split("?")[0] or "mod.jar"
    dest = mods_path / filename
    try:
        urlreq.urlretrieve(url, str(dest))
    except Exception as e:
        return {"ok": False, "msg": f"Download fejl: {e}"}
    return {"ok": True, "msg": f"{filename} installeret"}

def delete_server_mod(server_id, filename):
    _, mods_path = _mods_dir(server_id)
    if not mods_path:
        return {"ok": False, "msg": "Server ikke fundet"}
    target = mods_path / Path(filename).name
    if not target.exists():
        return {"ok": False, "msg": "Fil ikke fundet"}
    target.unlink()
    return {"ok": True, "msg": f"{filename} slettet"}
