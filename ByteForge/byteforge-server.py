#!/usr/bin/env python3
"""
ByteForge Backend API
Run with: sudo python3 byteforge-server.py

ByteForge is intentionally CasaOS-independent. Docker is used as the default
runtime for game servers because it keeps setup, limits and restarts simple.
"""

import json
import os
import shlex
import shutil
import subprocess
import time
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("BYTEFORGE_PORT", "8080"))
DEFAULT_HOME = "/opt/byteforge" if os.geteuid() == 0 else str(Path.home() / ".byteforge")
BASE_DIR = Path(os.environ.get("BYTEFORGE_HOME", DEFAULT_HOME))
CONFIG_PATH = Path(os.environ.get("BYTEFORGE_CONFIG", str(BASE_DIR / "servers.json")))
FILES_ROOT = Path(os.environ.get("BYTEFORGE_FILES", str(BASE_DIR / "files")))
PUBLIC_ROOT = FILES_ROOT / "public"
PRIVATE_ROOT = FILES_ROOT / "private"
SERVER_ROOT = FILES_ROOT / "servers"
SHARED_ROOT = FILES_ROOT / "shared"

SERVER_TYPES = {
    "minecraft-vanilla": {
        "name": "Minecraft Vanilla",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "VANILLA"},
        "ports": ["25565:25565"],
        "data": "/data",
    },
    "minecraft-paper": {
        "name": "Minecraft Paper",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "PAPER"},
        "ports": ["25565:25565"],
        "data": "/data",
    },
    "minecraft-spigot": {
        "name": "Minecraft Spigot",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "SPIGOT"},
        "ports": ["25565:25565"],
        "data": "/data",
    },
    "minecraft-forge": {
        "name": "Minecraft Forge",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "FORGE"},
        "ports": ["25565:25565"],
        "data": "/data",
    },
    "minecraft-fabric": {
        "name": "Minecraft Fabric",
        "image": "itzg/minecraft-server",
        "env": {"EULA": "TRUE", "TYPE": "FABRIC"},
        "ports": ["25565:25565"],
        "data": "/data",
    },
    "fivem": {
        "name": "FiveM",
        "image": "spritsail/fivem",
        "env": {},
        "ports": ["30120:30120/tcp", "30120:30120/udp"],
        "data": "/config",
    },
    "terraria": {
        "name": "Terraria",
        "image": "ryshe/terraria",
        "env": {"WORLD_FILENAME": "byteforge.wld"},
        "ports": ["7777:7777"],
        "data": "/root/.local/share/Terraria/Worlds",
    },
    "custom": {
        "name": "Custom Game Server",
        "image": "ubuntu:latest",
        "env": {},
        "ports": [],
        "data": "/data",
    },
}


def ensure_dirs():
    for path in (BASE_DIR, FILES_ROOT, PUBLIC_ROOT, PRIVATE_ROOT, SERVER_ROOT, SHARED_ROOT):
        path.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config({"servers": default_servers(), "users": default_users(), "settings": default_settings()})


def default_servers():
    return [
        {
            "id": "minecraft-main",
            "name": "Minecraft Main",
            "type": "minecraft-paper",
            "container": "byteforge-minecraft-main",
            "port": 25565,
            "cpu_limit": "2",
            "memory_limit": "4g",
            "auto_restart": True,
            "owner": "lucas",
            "visibility": "shared",
            "path": str(SERVER_ROOT / "minecraft-main"),
        }
    ]


def default_users():
    return [
        {"id": "lucas", "name": "Lucas", "role": "owner", "access": ["*"]},
        {"id": "guest", "name": "Guest", "role": "viewer", "access": ["public"]},
    ]


def default_settings():
    return {"theme": "forge-dark", "language": "da", "background": "grid", "website_hosting": True}


def load_config():
    ensure_dirs()
    try:
        with CONFIG_PATH.open() as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("servers", default_servers())
    data.setdefault("users", default_users())
    data.setdefault("settings", default_settings())
    return data


def save_config(data):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(CONFIG_PATH)


def run(cmd, timeout=10, shell=True):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as exc:
        return "", str(exc), 1


def docker_available():
    _, _, code = run(["docker", "version"], timeout=4, shell=False)
    return code == 0


def docker_status(container):
    out, _, code = run(["docker", "inspect", "--format={{.State.Status}}", container], timeout=5, shell=False)
    return out if code == 0 and out else "stopped"


def docker_logs(container, tail=30):
    out, err, _ = run(["docker", "logs", f"--tail={tail}", container], timeout=8, shell=False)
    return out or err


def docker_stats(container):
    fmt = "{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}"
    out, _, code = run(["docker", "stats", "--no-stream", "--format", fmt, container], timeout=6, shell=False)
    if code != 0 or "|" not in out:
        return {"cpu": "-", "memory": "-", "network": "-"}
    cpu, memory, network = out.split("|", 2)
    return {"cpu": cpu, "memory": memory, "network": network}


def slugify(value):
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return "-".join(part for part in clean.split("-") if part)[:48] or f"server-{int(time.time())}"


def get_system():
    cpu_out, _, _ = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    if not cpu_out:
        cpu_out, _, _ = run("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
    try:
        cpu = round(float(cpu_out), 1)
    except Exception:
        cpu = 0

    with open("/proc/meminfo") as f:
        mem = {line.split(":")[0]: int(line.split(":")[1].strip().split()[0]) for line in f if ":" in line}
    total = mem.get("MemTotal", 0)
    avail = mem.get("MemAvailable", 0)
    used = total - avail

    temp_out, _, _ = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try:
        temp = round(int(temp_out) / 1000, 1)
    except Exception:
        temp_alt, _, _ = run("sensors 2>/dev/null | grep 'Core 0' | awk '{print $3}' | tr -d '+°C'")
        temp = temp_alt or "?"

    uptime_s = int(open("/proc/uptime").read().split()[0].split(".")[0])
    h, m = divmod(uptime_s // 60, 60)
    d, h = divmod(h, 24)
    uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"

    return {
        "cpu": cpu,
        "ram_used_mb": used // 1024,
        "ram_total_mb": total // 1024,
        "ram_pct": round(used / total * 100, 1) if total else 0,
        "temp": temp,
        "uptime": uptime,
    }


def get_disks():
    disks = []
    out, _, _ = run(f"df -BG / {shlex.quote(str(FILES_ROOT))} 2>/dev/null || df -BG /")
    seen = set()
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 6 and parts[5] not in seen:
            seen.add(parts[5])
            disks.append({
                "mount": parts[5],
                "total": parts[1].replace("G", ""),
                "used": parts[2].replace("G", ""),
                "free": parts[3].replace("G", ""),
                "pct": parts[4].replace("%", ""),
            })
    return disks


def get_raid():
    md, _, _ = run("cat /proc/mdstat 2>/dev/null")
    if not md or "md" not in md:
        return {"status": "inactive", "info": "Ingen RAID konfigureret"}
    info = [line.strip() for line in md.splitlines() if line.strip()]
    state = "active" if "active" in md else "degraded" if "degraded" in md else "unknown"
    return {"status": state, "info": "\n".join(info[:6])}


def get_nas():
    exports, _, _ = run("cat /etc/exports 2>/dev/null")
    active, _, _ = run("systemctl is-active nfs-server 2>/dev/null || systemctl is-active nfs-kernel-server 2>/dev/null")
    shares = [line.strip() for line in exports.splitlines() if line.strip() and not line.startswith("#")]
    return {"status": active.strip(), "shares": shares, "path": str(SHARED_ROOT)}


def get_docker():
    out, _, _ = run("docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}' 2>/dev/null")
    containers = []
    for line in out.splitlines():
        if "|" in line:
            name, status, image = line.split("|", 2)
            containers.append({"name": name, "status": status, "image": image})
    return containers


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


def game_action(server_id, action):
    server = next((s for s in load_config()["servers"] if s["id"] == server_id), None)
    if not server:
        return {"ok": False, "msg": "Server ikke fundet"}
    if action not in ("start", "stop", "restart"):
        return {"ok": False, "msg": "Ukendt kommando"}
    out, err, code = run(["docker", action, server["container"]], timeout=45, shell=False)
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

    port = int(body.get("port") or (profile["ports"][0].split(":", 1)[0].split("/", 1)[0] if profile["ports"] else 0) or 0)
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
        "owner": body.get("owner") or "lucas",
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

    out, err, code = run(cmd, timeout=120, shell=False)
    return {"ok": code == 0, "server": server, "msg": out or err or "Server oprettet"}


def safe_path(scope, rel=""):
    roots = {
        "public": PUBLIC_ROOT,
        "private": PRIVATE_ROOT,
        "shared": SHARED_ROOT,
        "servers": SERVER_ROOT,
    }
    config = load_config()
    for server in config["servers"]:
        roots[server["id"]] = Path(server["path"])
    root = roots.get(scope, PUBLIC_ROOT).resolve()
    target = (root / rel.lstrip("/")).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Ugyldig sti")
    return root, target


def list_files(scope, rel=""):
    _, target = safe_path(scope, rel)
    target.mkdir(parents=True, exist_ok=True)
    if not target.is_dir():
        return {"path": rel, "items": []}
    items = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        stat = entry.stat()
        items.append({
            "name": entry.name,
            "type": "folder" if entry.is_dir() else "file",
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
        })
    return {"path": rel, "items": items}


def search_files(scope, query):
    root, _ = safe_path(scope, "")
    matches = []
    if not query:
        return matches
    for path in root.rglob("*"):
        if query.lower() in path.name.lower():
            matches.append({"path": str(path.relative_to(root)), "type": "folder" if path.is_dir() else "file"})
        if len(matches) >= 100:
            break
    return matches


def file_action(body):
    action = body.get("action")
    scope = body.get("scope", "public")
    path = body.get("path", "")
    _, target = safe_path(scope, path)
    if action == "mkdir":
        target.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "msg": "Mappe oprettet"}
    if action == "delete":
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return {"ok": True, "msg": "Slettet"}
    if action == "move":
        _, dest = safe_path(scope, body.get("dest", ""))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(dest))
        return {"ok": True, "msg": "Flyttet"}
    if action == "search":
        return {"ok": True, "matches": search_files(scope, body.get("query", ""))}
    return {"ok": False, "msg": "Ukendt filhandling"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/api/system":
                self.send_json(get_system())
            elif path == "/api/disks":
                self.send_json(get_disks())
            elif path == "/api/raid":
                self.send_json(get_raid())
            elif path == "/api/nas":
                self.send_json(get_nas())
            elif path == "/api/minecraft":
                self.send_json(legacy_minecraft())
            elif path == "/api/docker":
                self.send_json(get_docker())
            elif path == "/api/game-servers":
                self.send_json({"types": SERVER_TYPES, "servers": get_game_servers(qs.get("logs", ["0"])[0] == "1")})
            elif path == "/api/files":
                self.send_json(list_files(qs.get("scope", ["public"])[0], qs.get("path", [""])[0]))
            elif path == "/api/users":
                data = load_config()
                self.send_json({"users": data["users"], "settings": data["settings"]})
            elif path == "/api/all":
                self.send_json({
                    "system": get_system(),
                    "disks": get_disks(),
                    "raid": get_raid(),
                    "nas": get_nas(),
                    "minecraft": legacy_minecraft(),
                    "docker": get_docker(),
                    "game_servers": get_game_servers(),
                })
            elif path in ("/", "/index.html"):
                html_path = Path(__file__).with_name("byteforge-platform.html")
                self.send_file(html_path, "text/html; charset=utf-8")
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        ctype = self.headers.get("Content-Type", "")
        try:
            if parsed.path == "/api/files/upload":
                raw = self.rfile.read(length)
                message = BytesParser(policy=email_policy).parsebytes(
                    b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw
                )
                fields = {}
                file_part = None
                for part in message.iter_parts():
                    name = part.get_param("name", header="content-disposition")
                    filename = part.get_filename()
                    if filename:
                        file_part = part
                    elif name:
                        fields[name] = part.get_content()
                if not file_part:
                    self.send_json({"ok": False, "msg": "Ingen fil modtaget"}, 400)
                    return
                scope = fields.get("scope", "public")
                rel = fields.get("path", "")
                _, folder = safe_path(scope, rel)
                folder.mkdir(parents=True, exist_ok=True)
                dest = folder / Path(file_part.get_filename()).name
                with dest.open("wb") as f:
                    f.write(file_part.get_payload(decode=True) or b"")
                self.send_json({"ok": True, "msg": "Upload færdig", "file": dest.name})
                return

            body = json.loads(self.rfile.read(length) or "{}")
            if parsed.path == "/api/minecraft/action":
                self.send_json(game_action("minecraft-main", body.get("action", "")))
            elif parsed.path == "/api/game-servers/action":
                self.send_json(game_action(body.get("id", ""), body.get("action", "")))
            elif parsed.path == "/api/game-servers/create":
                self.send_json(create_game_server(body))
            elif parsed.path == "/api/files/action":
                self.send_json(file_action(body))
            elif parsed.path == "/api/settings":
                data = load_config()
                data["settings"].update(body)
                save_config(data)
                self.send_json({"ok": True, "settings": data["settings"]})
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)


if __name__ == "__main__":
    ensure_dirs()
    print("\033[38;5;208m")
    print("  ByteForge Platform starter på port", PORT)
    print("  Data:", BASE_DIR)
    print("\033[0m")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stoppet.")
