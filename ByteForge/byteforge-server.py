#!/usr/bin/env python3
"""
ByteForge Backend API
Run with: sudo python3 byteforge-server.py

Docker is used as the default runtime for game servers because it keeps setup, limits and restarts simple.
"""

import json
import mimetypes
import shlex
import threading
import time
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from api.config import (
    PORT, BASE_DIR, PLATFORM, STATIC_FILES,
    load_config, save_config, ensure_dirs,
)
from api.state import (
    SESSION_COOKIE, SESSION_TTL,
    _METRICS_HISTORY, _METRICS_LOCK,
    BACKUP_DIR,
)
from api.utils import run, docker_available
from api.system import get_system, get_disks, get_raid, get_hardware, exec_command
from api.network import (
    get_network, get_network_devices, get_uptime_with_history,
    get_uptime_checks, webhook_save, webhook_test, webhook_get,
    _uptime_collector,
)
from api.nas import get_nas, nas_setup, nas_setup_samba, nas_remove_share, nas_service_action
from api.apps import APP_CATALOG, get_appstore, appstore_install, appstore_install_logs, appstore_uninstall
from api.docker_mgr import get_docker, docker_container_action
from api.game import (
    SERVER_TYPES, get_game_servers, legacy_minecraft,
    game_action, create_game_server, delete_game_server,
    list_server_mods, install_server_mod, delete_server_mod,
)
from api.auth import (
    _session_user, auth_enabled, auth_status, auth_setup,
    auth_login, auth_logout, auth_change_password,
    auth_2fa_setup, auth_2fa_enable,
)
from api.files import safe_path, list_files, search_files, file_action
from api.proxy import (
    get_proxy, create_proxy_host, delete_proxy_host,
    apply_proxy, proxy_action, deploy_nginx_proxy_manager,
)
from api.privacy import PRIVACY_APPS, deploy_app
from api.backup import load_backup_jobs, save_backup_jobs, list_restore_points, run_backup_job
from api.metrics import _metrics_collector, setup_status, install_docker_system, install_service_system
from api.system import get_smart


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_cors_headers(self):
        origin = self.headers.get("Origin")
        self.send_header("Access-Control-Allow-Origin", origin or "*")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def send_json(self, data, code=200, headers=None):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        for key, value in (headers or {}).items():
            self.send_header(key, value)
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
        self.send_cors_headers()
        self.end_headers()

    def auth_required(self, path):
        if not path.startswith("/api/"):
            return False
        if path in ("/api/auth/status", "/api/auth/login", "/api/auth/setup", "/api/background"):
            return False
        return auth_enabled()

    def ensure_authenticated(self, path):
        if not self.auth_required(path):
            return True
        if _session_user(self):
            return True
        self.send_json({"ok": False, "error": "Unauthorized"}, 401)
        return False

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if not self.ensure_authenticated(path):
                return
            if path == "/api/auth/status":
                self.send_json(auth_status(self))
            elif path == "/api/system":
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
            elif path == "/api/hardware":
                self.send_json(get_hardware())
            elif path == "/api/setup":
                self.send_json(setup_status())
            elif path == "/api/network":
                self.send_json(get_network())
            elif path == "/api/proxy":
                self.send_json(get_proxy())
            elif path == "/api/game-servers":
                self.send_json({"types": SERVER_TYPES, "servers": get_game_servers(qs.get("logs", ["0"])[0] == "1")})
            elif path.startswith("/api/game-servers/") and path.endswith("/mods"):
                server_id = path.split("/")[3]
                self.send_json(list_server_mods(server_id))
            elif path == "/api/files":
                self.send_json(list_files(qs.get("scope", ["public"])[0], qs.get("path", [""])[0]))
            elif path == "/api/users":
                data = load_config()
                self.send_json({"users": data["users"], "settings": data["settings"]})
            elif path == "/api/all":
                self.send_json({
                    "system": get_system(),
                    "hardware": get_hardware(),
                    "disks": get_disks(),
                    "raid": get_raid(),
                    "nas": get_nas(),
                    "minecraft": legacy_minecraft(),
                    "docker": get_docker(),
                    "game_servers": get_game_servers(),
                    "network": get_network(),
                })
            elif path == "/api/backup/jobs":
                jobs = load_backup_jobs()
                rp = list_restore_points()
                self.send_json({"jobs": jobs, "restore_points": rp, "backup_dir": str(BACKUP_DIR)})
            elif path == "/api/metrics/history":
                with _METRICS_LOCK:
                    self.send_json(list(_METRICS_HISTORY))
            elif path == "/api/smart":
                self.send_json(get_smart())
            elif path == "/api/uptime":
                self.send_json(get_uptime_with_history())
            elif path == "/api/network/devices":
                self.send_json(get_network_devices())
            elif path == "/api/webhook":
                self.send_json(webhook_get())
            elif path == "/api/appstore":
                self.send_json(get_appstore())
            elif path == "/api/appstore/logs":
                self.send_json(appstore_install_logs(qs.get("app", [""])[0]))
            elif path == "/api/background":
                for ext in ("jpg", "jpeg", "png", "gif", "webp"):
                    p = BASE_DIR / f"background.{ext}"
                    if p.exists():
                        self.send_file(p, f"image/{ext}")
                        return
                self.send_json({"error": "No background image set"}, 404)
            elif path in STATIC_FILES:
                asset_path = Path(__file__).with_name(STATIC_FILES[path])
                if not asset_path.exists():
                    self.send_json({"error": "Asset not found"}, 404)
                    return
                mime = mimetypes.guess_type(str(asset_path))[0] or "application/octet-stream"
                if asset_path.suffix == ".js":
                    mime = "application/javascript; charset=utf-8"
                elif asset_path.suffix == ".css":
                    mime = "text/css; charset=utf-8"
                self.send_file(asset_path, mime)
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
            if not self.ensure_authenticated(parsed.path):
                return
            if parsed.path in ("/api/files/upload", "/api/background/upload"):
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
                if parsed.path == "/api/background/upload":
                    ext = Path(file_part.get_filename()).suffix.lower() or ".jpg"
                    for old_ext in ("jpg", "jpeg", "png", "gif", "webp"):
                        old_p = BASE_DIR / f"background.{old_ext}"
                        if old_p.exists():
                            old_p.unlink()
                    dest = BASE_DIR / f"background{ext}"
                    with dest.open("wb") as f:
                        f.write(file_part.get_payload(decode=True) or b"")
                    cfg = load_config()
                    cfg["settings"]["background"] = "/api/background"
                    save_config(cfg)
                    self.send_json({"ok": True, "url": "/api/background"})
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
            if parsed.path == "/api/auth/setup":
                self.send_json(auth_setup(body))
            elif parsed.path == "/api/auth/login":
                token, result = auth_login(body)
                headers = {}
                if token:
                    headers["Set-Cookie"] = f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}"
                self.send_json(result, 200 if result.get("ok") else 401, headers=headers)
            elif parsed.path == "/api/auth/logout":
                self.send_json(auth_logout(self), headers={"Set-Cookie": f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})
            elif parsed.path == "/api/auth/password":
                self.send_json(auth_change_password(self, body))
            elif parsed.path == "/api/auth/2fa/setup":
                self.send_json(auth_2fa_setup(self))
            elif parsed.path == "/api/auth/2fa/enable":
                self.send_json(auth_2fa_enable(self, body))
            elif parsed.path == "/api/minecraft/action":
                self.send_json(game_action("minecraft-main", body.get("action", "")))
            elif parsed.path == "/api/game-servers/action":
                self.send_json(game_action(body.get("id", ""), body.get("action", "")))
            elif parsed.path == "/api/game-servers/create":
                self.send_json(create_game_server(body))
            elif parsed.path == "/api/game-servers/delete":
                self.send_json(delete_game_server(body.get("id", "")))
            elif parsed.path == "/api/game-servers/mods/install":
                self.send_json(install_server_mod(body.get("server_id",""), body.get("url"), body.get("modrinth_slug")))
            elif parsed.path == "/api/game-servers/mods/delete":
                self.send_json(delete_server_mod(body.get("server_id",""), body.get("filename","")))
            elif parsed.path == "/api/ai/ollama":
                import urllib.request as _ur, json as _j
                payload = _j.dumps({"model": body.get("model","llama3"), "prompt": body.get("prompt",""), "stream": False}).encode()
                try:
                    req = _ur.Request("http://localhost:11434/api/generate", data=payload, headers={"Content-Type":"application/json"}, method="POST")
                    with _ur.urlopen(req, timeout=60) as r:
                        self.send_json(_j.loads(r.read()))
                except Exception as e:
                    self.send_json({"ok": False, "error": str(e), "response": f"Ollama fejl: {e}"})
            elif parsed.path == "/api/files/action":
                self.send_json(file_action(body))
            elif parsed.path == "/api/settings":
                data = load_config()
                data["settings"].update(body)
                save_config(data)
                self.send_json({"ok": True, "settings": data["settings"]})
            elif parsed.path == "/api/setup/docker":
                self.send_json(install_docker_system())
            elif parsed.path == "/api/setup/service":
                self.send_json(install_service_system())
            elif parsed.path == "/api/docker/action":
                self.send_json(docker_container_action(body.get("container", ""), body.get("action", "")))
            elif parsed.path == "/api/proxy/hosts/create":
                self.send_json(create_proxy_host(body))
            elif parsed.path == "/api/proxy/hosts/delete":
                self.send_json(delete_proxy_host(body))
            elif parsed.path == "/api/proxy/apply":
                self.send_json(apply_proxy())
            elif parsed.path == "/api/proxy/action":
                self.send_json(proxy_action(body))
            elif parsed.path == "/api/proxy/npm/deploy":
                self.send_json(deploy_nginx_proxy_manager())
            elif parsed.path == "/api/nas/action":
                self.send_json(nas_service_action(body.get("action", "restart")))
            elif parsed.path == "/api/webhook/save":
                self.send_json(webhook_save(body.get("url", "")))
            elif parsed.path == "/api/webhook/test":
                self.send_json(webhook_test(body.get("url", "")))
            elif parsed.path == "/api/nas/setup":
                self.send_json(nas_setup(
                    body.get("path", "/mnt/nas-share"),
                    body.get("subnet", "0.0.0.0/0"),
                    body.get("readonly", False),
                    body.get("smb_user", ""),
                    body.get("smb_pass", "")))
            elif parsed.path == "/api/nas/remove":
                self.send_json(nas_remove_share(body.get("path", "")))
            elif parsed.path == "/api/apps/deploy":
                self.send_json(deploy_app(body.get("app", "")))
            elif parsed.path == "/api/appstore/install":
                self.send_json(appstore_install(body.get("app", "")))
            elif parsed.path == "/api/appstore/uninstall":
                self.send_json(appstore_uninstall(body.get("app", "")))
            elif parsed.path == "/api/backup/add":
                jobs = load_backup_jobs()
                new_job = {
                    "id": f"job-{int(time.time())}",
                    "name": body.get("name", "Backup"),
                    "src": body.get("src", ""),
                    "schedule": body.get("schedule", "manual"),
                    "last_run": None,
                    "last_size_mb": None,
                }
                jobs.append(new_job)
                save_backup_jobs(jobs)
                self.send_json({"ok": True, "job": new_job})
            elif parsed.path == "/api/backup/delete":
                jobs = [j for j in load_backup_jobs() if j.get("id") != body.get("id")]
                save_backup_jobs(jobs)
                self.send_json({"ok": True})
            elif parsed.path == "/api/backup/run":
                job_id = body.get("id")
                job = next((j for j in load_backup_jobs() if j.get("id") == job_id), None)
                if not job:
                    self.send_json({"ok": False, "msg": "Job ikke fundet"})
                else:
                    self.send_json(run_backup_job(job))
            elif parsed.path == "/api/backup/restore":
                path_str = body.get("path", "")
                dest = body.get("dest", str(BASE_DIR / "restore"))
                p = Path(path_str)
                if not p.exists():
                    self.send_json({"ok": False, "msg": "Fil ikke fundet"})
                else:
                    Path(dest).mkdir(parents=True, exist_ok=True)
                    out, err, code = run(f"tar -xzf {shlex.quote(path_str)} -C {shlex.quote(dest)} 2>&1", timeout=120, shell=True)
                    self.send_json({"ok": code == 0, "msg": out or err or f"Gendannet til {dest}"})
            elif parsed.path == "/api/terminal/exec":
                self.send_json(exec_command(body.get("cmd", "")))
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, 500)


if __name__ == "__main__":
    ensure_dirs()
    def _guarded_metrics():
        while True:
            try:
                _metrics_collector()
            except Exception:
                pass
            time.sleep(1)
    threading.Thread(target=_guarded_metrics, daemon=True).start()
    threading.Thread(target=_uptime_collector, daemon=True).start()
    print("\033[38;5;208m")
    print("  ByteForge Platform starter på port", PORT)
    print("  Data:", BASE_DIR)
    print("\033[0m")
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stoppet.")
