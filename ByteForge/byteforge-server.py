#!/usr/bin/env python3
"""
ByteForge Backend API
Kør med: sudo python3 byteforge-server.py
"""

import json, os, subprocess, shutil, glob
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8080

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except:
        return ""

def get_system():
    cpu = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'") or \
          run("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
    try: cpu = round(float(cpu), 1)
    except: cpu = 0

    with open('/proc/meminfo') as f:
        mem = {l.split(':')[0]: int(l.split(':')[1].strip().split()[0]) for l in f if ':' in l}
    total = mem.get('MemTotal', 0)
    avail = mem.get('MemAvailable', 0)
    used  = total - avail

    temp = run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
    try: temp = round(int(temp) / 1000, 1)
    except: temp = run("sensors 2>/dev/null | grep 'Core 0' | awk '{print $3}' | tr -d '+°C'") or "?"

    uptime_s = int(open('/proc/uptime').read().split()[0].split('.')[0])
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
    lines = run("df -BG / /mnt/nas-share /mnt/raid 2>/dev/null || df -BG /").splitlines()
    seen = set()
    for l in lines[1:]:
        p = l.split()
        if len(p) >= 6 and p[5] not in seen:
            seen.add(p[5])
            disks.append({
                "mount": p[5],
                "total": p[1].replace('G',''),
                "used": p[2].replace('G',''),
                "free": p[3].replace('G',''),
                "pct": p[4].replace('%',''),
            })
    return disks

def get_raid():
    md = run("cat /proc/mdstat 2>/dev/null")
    if not md or 'md' not in md:
        return {"status": "inactive", "info": "Ingen RAID konfigureret"}
    lines = md.splitlines()
    info = []
    for l in lines:
        if l.strip(): info.append(l.strip())
    state = "active" if "active" in md else "degraded" if "degraded" in md else "unknown"
    return {"status": state, "info": "\n".join(info[:6])}

def get_nas():
    exports = run("cat /etc/exports 2>/dev/null")
    active = run("systemctl is-active nfs-server 2>/dev/null || systemctl is-active nfs-kernel-server 2>/dev/null")
    shares = []
    for l in exports.splitlines():
        if l.strip() and not l.startswith('#'):
            shares.append(l.strip())
    return {
        "status": active.strip(),
        "shares": shares,
        "path": "/mnt/nas-share",
    }

def get_minecraft():
    status = run("docker inspect --format='{{.State.Status}}' minecraft-server 2>/dev/null")
    logs   = run("docker logs --tail=8 minecraft-server 2>/dev/null") if status == "running" else ""
    players = ""
    if status == "running":
        players = run("docker exec minecraft-server rcon-cli list 2>/dev/null") or ""
    return {
        "status": status or "stopped",
        "logs": logs,
        "players": players,
        "port": 25565,
    }

def get_docker():
    out = run("docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}'")
    containers = []
    for l in out.splitlines():
        if '|' in l:
            parts = l.split('|')
            containers.append({"name": parts[0], "status": parts[1], "image": parts[2]})
    return containers

def minecraft_action(action):
    if action == "start":
        r = run("docker start minecraft-server 2>&1")
        return {"ok": True, "msg": r or "Server starter..."}
    elif action == "stop":
        r = run("docker stop minecraft-server 2>&1")
        return {"ok": True, "msg": r or "Server stopper..."}
    elif action == "restart":
        r = run("docker restart minecraft-server 2>&1")
        return {"ok": True, "msg": r or "Server genstarter..."}
    return {"ok": False, "msg": "Ukendt kommando"}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path

        routes = {
            '/api/system':    lambda: self.send_json(get_system()),
            '/api/disks':     lambda: self.send_json(get_disks()),
            '/api/raid':      lambda: self.send_json(get_raid()),
            '/api/nas':       lambda: self.send_json(get_nas()),
            '/api/minecraft': lambda: self.send_json(get_minecraft()),
            '/api/docker':    lambda: self.send_json(get_docker()),
            '/api/all':       lambda: self.send_json({
                "system": get_system(), "disks": get_disks(),
                "raid": get_raid(), "nas": get_nas(),
                "minecraft": get_minecraft(), "docker": get_docker()
            }),
        }

        if path in routes:
            routes[path]()
        elif path in ('/', '/index.html'):
            html_path = os.path.join(os.path.dirname(__file__), 'byteforge-site.html')
            if os.path.exists(html_path):
                self.send_file(html_path, 'text/html; charset=utf-8')
            else:
                self.send_json({"error": "byteforge-site.html not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        p = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length) or '{}')

        if p.path == '/api/minecraft/action':
            action = body.get('action', '')
            self.send_json(minecraft_action(action))
        else:
            self.send_json({"error": "Not found"}, 404)

if __name__ == '__main__':
    print(f"\033[38;5;208m")
    print("  ⚒  ByteForge Server starter på port", PORT, " ⚒")
    print(f"\033[0m")
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stoppet.")
