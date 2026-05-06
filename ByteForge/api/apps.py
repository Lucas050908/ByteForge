import subprocess
import threading

from api.config import SERVER_ROOT
from api.utils import run, docker_available, container_exists, docker_status
from api.state import _INSTALL_LOGS

APP_CATALOG = {
    # ── Media ──                                                                                    webport = host port the browser should open
    "jellyfin":         {"name":"Jellyfin",          "icon":"🎬","desc":"Open-source media server. Stream movies, TV, music.",                 "category":"Media",       "image":"jellyfin/jellyfin:latest",                        "ports":["8096:8096"],                           "webport":"8096", "data":"/config","env":{}},
    "plex":             {"name":"Plex",               "icon":"🎥","desc":"Premium media server with mobile apps and transcoding.",               "category":"Media",       "image":"plexinc/pms-docker",                              "ports":["32400:32400"],                         "webport":"32400","data":"/config","env":{"TZ":"Europe/Copenhagen"}},
    "navidrome":        {"name":"Navidrome",          "icon":"🎵","desc":"Modern music server. Subsonic-compatible API.",                        "category":"Media",       "image":"deluan/navidrome:latest",                         "ports":["4533:4533"],                           "webport":"4533", "data":"/data","env":{}},
    "photoprism":       {"name":"Photoprism",         "icon":"📸","desc":"AI-powered photo management. Google Photos alternative.",             "category":"Media",       "image":"photoprism/photoprism:latest",                    "ports":["2342:2342"],                           "webport":"2342", "data":"/photoprism/storage","env":{"PHOTOPRISM_AUTH_MODE":"public"}},
    "immich":           {"name":"Immich",             "icon":"🖼","desc":"High performance self-hosted photo and video backup.",                 "category":"Media",       "image":"ghcr.io/immich-app/immich-server:release",        "ports":["2283:3001"],                           "webport":"2283", "data":"/usr/src/app/upload","env":{}},
    # ── Development ──
    "vscode-server":    {"name":"VS Code Server",     "icon":"💻","desc":"Full VS Code IDE running in your browser.",                           "category":"Development", "image":"codercom/code-server:latest",                     "ports":["8443:8080"],                           "webport":"8443", "data":"/home/coder","user":"root","env":{"PASSWORD":"byteforge"}},
    "gitea":            {"name":"Gitea",              "icon":"🦊","desc":"Lightweight self-hosted Git service. GitHub alternative.",            "category":"Development", "image":"gitea/gitea:latest",                              "ports":["3000:3000","222:22"],                  "webport":"3000", "data":"/data","env":{}},
    "portainer":        {"name":"Portainer",          "icon":"🐋","desc":"Docker management UI. Manage containers, images, volumes.",           "category":"Development", "image":"portainer/portainer-ce:latest",                   "ports":["9000:9000"],                           "webport":"9000", "data":"/data","env":{}},
    "registry":         {"name":"Docker Registry",   "icon":"📦","desc":"Private Docker image registry.",                                      "category":"Development", "image":"registry:2",                                      "ports":["5000:5000"],                           "webport":"",     "data":"/var/lib/registry","env":{}},
    "drone":            {"name":"Drone CI",           "icon":"🚀","desc":"Container-native CI/CD platform.",                                    "category":"Development", "image":"drone/drone:latest",                              "ports":["3005:80"],                             "webport":"3005", "data":"/data","env":{}},
    # ── Network ──
    "nginx-pm":         {"name":"Nginx Proxy Mgr",   "icon":"🌐","desc":"Reverse proxy with SSL GUI. Admin UI on port 81.",                   "category":"Network",     "image":"jc21/nginx-proxy-manager:latest",                 "ports":["80:80","81:81","443:443"],             "webport":"81",   "data":"/data","env":{}},
    "adguard":          {"name":"AdGuard Home",       "icon":"🛡","desc":"Network-wide ad & tracker blocker. Pi-hole alternative.",            "category":"Network",     "image":"adguard/adguardhome:latest",                      "ports":["53:53/udp","3001:3000"],               "webport":"3001", "data":"/opt/adguardhome/work","env":{}},
    "traefik":          {"name":"Traefik",            "icon":"🔀","desc":"Modern reverse proxy & load balancer with auto SSL.",                "category":"Network",     "image":"traefik:latest",                                  "ports":["80:80","443:443","18080:8080"],        "webport":"18080","data":"/etc/traefik","env":{}},
    "wireguard":        {"name":"WireGuard VPN",      "icon":"🔒","desc":"Fast, modern VPN server. Access your homelab from anywhere.",        "category":"Network",     "image":"linuxserver/wireguard",                           "ports":["51820:51820/udp"],                     "webport":"",     "data":"/config","env":{"PUID":"1000","PGID":"1000","TZ":"Europe/Copenhagen"}},
    "cloudflared":      {"name":"Cloudflare Tunnel",  "icon":"☁","desc":"Expose services without opening ports. Zero Trust tunnels.",          "category":"Network",     "image":"cloudflare/cloudflared:latest",                   "ports":[],                                      "webport":"",     "data":"/etc/cloudflared","env":{}},
    # ── Cloud Storage ──
    "nextcloud":        {"name":"Nextcloud",          "icon":"☁","desc":"Your private cloud. Files, calendar, contacts and more.",             "category":"Cloud",       "image":"nextcloud:latest",                                "ports":["8888:80"],                             "webport":"8888", "data":"/var/www/html","env":{}},
    "syncthing":        {"name":"Syncthing",          "icon":"🔄","desc":"Continuous file synchronization across all your devices.",           "category":"Cloud",       "image":"syncthing/syncthing:latest",                      "ports":["8384:8384","22000:22000"],             "webport":"8384", "data":"/var/syncthing","env":{}},
    "duplicati":        {"name":"Duplicati",          "icon":"💾","desc":"Backup to cloud storage with encryption and scheduling.",            "category":"Cloud",       "image":"lscr.io/linuxserver/duplicati:latest",            "ports":["8200:8200"],                           "webport":"8200", "data":"/config","env":{}},
    # ── Monitoring ──
    "grafana":          {"name":"Grafana",            "icon":"📊","desc":"Analytics & monitoring dashboards. Connect any data source.",        "category":"Monitoring",  "image":"grafana/grafana:latest",                          "ports":["3010:3000"],                           "webport":"3010", "data":"/var/lib/grafana","env":{}},
    "prometheus":       {"name":"Prometheus",         "icon":"🔥","desc":"Metrics collection & alerting toolkit.",                             "category":"Monitoring",  "image":"prom/prometheus:latest",                          "ports":["9090:9090"],                           "webport":"9090", "data":"/prometheus","env":{}},
    "uptime-kuma":      {"name":"Uptime Kuma",        "icon":"💓","desc":"Self-hosted uptime monitor. Check websites and services.",           "category":"Monitoring",  "image":"louislam/uptime-kuma:1",                          "ports":["3011:3001"],                           "webport":"3011", "data":"/app/data","env":{}},
    "netdata":          {"name":"Netdata",            "icon":"📈","desc":"Real-time performance monitoring. Zero config required.",            "category":"Monitoring",  "image":"netdata/netdata:latest",                          "ports":["19999:19999"],                         "webport":"19999","data":"/var/lib/netdata","env":{}},
    # ── Security ──
    "bitwarden":        {"name":"Bitwarden",          "icon":"🔑","desc":"Self-hosted password manager. Sync across all devices.",             "category":"Security",    "image":"vaultwarden/server:latest",                       "ports":["8081:80"],                             "webport":"8081", "data":"/data","env":{}},
    "authelia":         {"name":"Authelia",           "icon":"🔐","desc":"SSO & 2FA portal for all your services.",                            "category":"Security",    "image":"authelia/authelia:latest",                        "ports":["9091:9091"],                           "webport":"9091", "data":"/config","env":{}},
    "pihole":           {"name":"Pi-hole",            "icon":"🌑","desc":"Network-wide ad blocking DNS server. Web UI on port 8089.",          "category":"Security",    "image":"pihole/pihole:latest",                            "ports":["53:53/tcp","53:53/udp","8089:80"],     "webport":"8089", "data":"/etc/pihole","env":{"TZ":"Europe/Copenhagen"}},
    "searxng":          {"name":"SearXNG",            "icon":"🔍","desc":"Privacy-respecting metasearch engine.",                              "category":"Security",    "image":"searxng/searxng:latest",                          "ports":["8082:8080"],                           "webport":"8082", "data":"/etc/searxng","env":{}},
    # ── Database ──
    "mysql":            {"name":"MySQL",              "icon":"🗄","desc":"World's most popular open source database.",                         "category":"Database",    "image":"mysql:8.0",                                       "ports":["3306:3306"],                           "webport":"",     "data":"/var/lib/mysql","env":{"MYSQL_ROOT_PASSWORD":"byteforge"}},
    "postgres":         {"name":"PostgreSQL",         "icon":"🐘","desc":"Advanced open source relational database.",                          "category":"Database",    "image":"postgres:15",                                     "ports":["5432:5432"],                           "webport":"",     "data":"/var/lib/postgresql/data","env":{"POSTGRES_PASSWORD":"byteforge"}},
    "redis":            {"name":"Redis",              "icon":"⚡","desc":"In-memory data structure store. Cache & message broker.",            "category":"Database",    "image":"redis:alpine",                                    "ports":["6379:6379"],                           "webport":"",     "data":"/data","env":{}},
    "mongodb":          {"name":"MongoDB",            "icon":"🍃","desc":"NoSQL document database for modern applications.",                   "category":"Database",    "image":"mongo:latest",                                    "ports":["27017:27017"],                         "webport":"",     "data":"/data/db","env":{}},
    "mariadb":          {"name":"MariaDB",            "icon":"🦭","desc":"MySQL-compatible database with extra features.",                     "category":"Database",    "image":"mariadb:latest",                                  "ports":["3307:3306"],                           "webport":"",     "data":"/var/lib/mysql","env":{"MARIADB_ROOT_PASSWORD":"byteforge"}},
    # ── Home Automation ──
    "homeassistant":    {"name":"Home Assistant",     "icon":"🏠","desc":"Open source home automation. Control everything from one place.",   "category":"Home",        "image":"homeassistant/home-assistant:stable",             "ports":["8123:8123"],                           "webport":"8123", "data":"/config","env":{}},
    "node-red":         {"name":"Node-RED",           "icon":"🔴","desc":"Flow-based programming for automation.",                             "category":"Home",        "image":"nodered/node-red:latest",                         "ports":["1880:1880"],                           "webport":"1880", "data":"/data","env":{}},
    "mosquitto":        {"name":"Mosquitto MQTT",     "icon":"📡","desc":"Lightweight MQTT message broker for IoT.",                          "category":"Home",        "image":"eclipse-mosquitto:latest",                        "ports":["1883:1883"],                           "webport":"",     "data":"/mosquitto/data","env":{}},
    # ── Productivity ──
    "bookstack":        {"name":"BookStack",          "icon":"📚","desc":"Simple wiki & documentation platform.",                              "category":"Productivity","image":"lscr.io/linuxserver/bookstack:latest",            "ports":["6875:80"],                             "webport":"6875", "data":"/config","env":{"APP_URL":"http://localhost:6875"}},
    "wikijs":           {"name":"Wiki.js",            "icon":"📖","desc":"Powerful, extensible open source wiki.",                            "category":"Productivity","image":"ghcr.io/requarks/wiki:2",                         "ports":["3004:3000"],                           "webport":"3004", "data":"/wiki/data","env":{}},
    "n8n":              {"name":"n8n",                "icon":"⚙","desc":"Workflow automation. Connect anything to anything.",                  "category":"Productivity","image":"n8nio/n8n:latest",                              "ports":["5678:5678"],                           "webport":"5678", "data":"/home/node/.n8n","env":{}},
    "paperless":        {"name":"Paperless-ngx",      "icon":"📄","desc":"Document management system. Go paperless.",                         "category":"Productivity","image":"ghcr.io/paperless-ngx/paperless-ngx:latest",    "ports":["8000:8000"],                           "webport":"8000", "data":"/usr/src/paperless/data","env":{}},
    "freshrss":         {"name":"FreshRSS",           "icon":"📰","desc":"Self-hosted RSS feed aggregator.",                                  "category":"Productivity","image":"freshrss/freshrss:latest",                       "ports":["8070:80"],                             "webport":"8070", "data":"/var/www/FreshRSS/data","env":{}},
    # ── AI ──
    "ollama":           {"name":"Ollama",             "icon":"🤖","desc":"Run LLMs locally. Llama, Mistral, Gemma and more.",                 "category":"AI",          "image":"ollama/ollama:latest",                            "ports":["11434:11434"],                         "webport":"",     "data":"/root/.ollama","env":{}},
    "open-webui":       {"name":"Open WebUI",         "icon":"💬","desc":"ChatGPT-like web interface for Ollama.",                            "category":"AI",          "image":"ghcr.io/open-webui/open-webui:main",              "ports":["3002:8080"],                           "webport":"3002", "data":"/app/backend/data","env":{"OLLAMA_BASE_URL":"http://host.docker.internal:11434"}},
    "stable-diffusion": {"name":"Stable Diffusion",   "icon":"🎨","desc":"AI image generation from text prompts.",                            "category":"AI",          "image":"universonic/stable-diffusion-webui:full",          "ports":["7860:7860"],                           "webport":"7860", "data":"/data","env":{}},
}


def get_appstore():
    apps = []
    for app_id, app in APP_CATALOG.items():
        container = f"byteforge-{app_id}"
        installed = container_exists(container)
        status = docker_status(container) if installed else "not_installed"
        if app_id in _INSTALL_LOGS and not _INSTALL_LOGS[app_id]["done"]:
            status = "installing"
        apps.append({**app, "id": app_id, "installed": installed, "status": status})
    return apps


def appstore_install(app_id):
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig"}
    app = APP_CATALOG.get(app_id)
    if not app:
        return {"ok": False, "msg": f"Ukendt app: {app_id}"}
    container = f"byteforge-{app_id}"
    if container_exists(container):
        return {"ok": False, "msg": f"{app['name']} er allerede installeret"}
    if app_id in _INSTALL_LOGS and not _INSTALL_LOGS[app_id]["done"]:
        return {"ok": False, "msg": "Installation already in progress"}
    _INSTALL_LOGS[app_id] = {"lines": [], "done": False, "ok": None}
    threading.Thread(target=_run_install, args=(app_id,), daemon=True).start()
    return {"ok": True, "msg": "started"}


def _run_install(app_id):
    app = APP_CATALOG[app_id]
    container = f"byteforge-{app_id}"
    state = _INSTALL_LOGS[app_id]
    def log(msg):
        state["lines"].append(msg)
    try:
        log(f"▶ Pulling {app['image']}...")
        proc = subprocess.Popen(
            ["docker", "pull", app["image"]],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in proc.stdout:
            stripped = line.rstrip()
            if stripped:
                log(stripped)
        proc.wait()
        if proc.returncode != 0:
            log("✗ Pull mislykkedes"); state["ok"] = False; return
        log("▶ Starter container...")
        data_path = SERVER_ROOT / "apps" / app_id
        data_path.mkdir(parents=True, exist_ok=True)
        cmd = ["docker", "run", "-d", "--name", container,
               "--label", "byteforge.app=true", "--restart", "unless-stopped"]
        if app.get("user"):
            cmd += ["--user", app["user"]]
        for k, v in app["env"].items():
            cmd += ["-e", f"{k}={v}"]
        for p in app["ports"]:
            cmd += ["-p", p]
        if app["data"]:
            cmd += ["-v", f"{data_path}:{app['data']}"]
        cmd.append(app["image"])
        out, err, code = run(cmd, timeout=30, shell=False)
        if code == 0:
            url = f"  →  http://localhost:{app['webport']}" if app.get("webport") else ""
            log(f"✓ {app['name']} installeret!{url}")
            state["ok"] = True
        else:
            log(f"✗ Fejl: {err or out}"); state["ok"] = False
    except Exception as e:
        log(f"✗ {e}"); state["ok"] = False
    finally:
        state["done"] = True


def appstore_install_logs(app_id):
    return _INSTALL_LOGS.get(app_id, {"lines": [], "done": True, "ok": None})


def appstore_uninstall(app_id):
    container = f"byteforge-{app_id}"
    if not container_exists(container):
        return {"ok": False, "msg": "Container ikke fundet"}
    out, err, code = run(["docker", "rm", "-f", container], timeout=15, shell=False)
    return {"ok": code == 0, "msg": out or err or "Afinstalleret"}
