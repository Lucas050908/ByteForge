from api.config import SERVER_ROOT
from api.utils import run, docker_available, container_exists

PRIVACY_APPS = {
    "bitwarden": {"name": "Bitwarden",  "image": "vaultwarden/server:latest",    "ports": ["8081:80"],                            "env": {},                                                        "data": "/data"},
    "nextcloud": {"name": "Nextcloud",  "image": "nextcloud:latest",              "ports": ["8888:80"],                            "env": {},                                                        "data": "/var/www/html"},
    "pihole":    {"name": "Pi-hole",    "image": "pihole/pihole:latest",          "ports": ["53:53/tcp", "53:53/udp", "8089:80"],  "env": {"TZ": "Europe/Copenhagen"},                               "data": "/etc/pihole"},
    "wireguard": {"name": "WireGuard",  "image": "linuxserver/wireguard",         "ports": ["51820:51820/udp"],                    "env": {"PUID": "1000", "PGID": "1000", "TZ": "Europe/Copenhagen"}, "data": "/config"},
    "portainer": {"name": "Portainer",  "image": "portainer/portainer-ce:latest", "ports": ["9000:9000"],                          "env": {},                                                        "data": "/data"},
    "grafana":   {"name": "Grafana",    "image": "grafana/grafana:latest",         "ports": ["3000:3000"],                          "env": {},                                                        "data": "/var/lib/grafana"},
    "jellyfin":  {"name": "Jellyfin",   "image": "jellyfin/jellyfin:latest",       "ports": ["8096:8096"],                          "env": {},                                                        "data": "/config"},
    "ollama":    {"name": "Ollama",     "image": "ollama/ollama:latest",           "ports": ["11434:11434"],                        "env": {},                                                        "data": "/root/.ollama"},
}


def deploy_app(app_id):
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig. Installer Docker først."}
    profile = PRIVACY_APPS.get(app_id)
    if not profile:
        return {"ok": False, "msg": f"Ukendt app: {app_id}"}
    container = f"byteforge-{app_id}"
    if container_exists(container):
        return {"ok": False, "msg": f"{profile['name']} kører allerede (container: {container})"}
    data_path = SERVER_ROOT / "apps" / app_id
    data_path.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "-d", "--name", container, "--label", "byteforge.app=true", "--restart", "unless-stopped"]
    for k, v in profile["env"].items():
        cmd += ["-e", f"{k}={v}"]
    for p in profile["ports"]:
        cmd += ["-p", p]
    cmd += ["-v", f"{data_path}:{profile['data']}", profile["image"]]
    out, err, code = run(cmd, timeout=300, shell=False)
    host_port = profile["ports"][0].split(":")[0] if profile["ports"] else ""
    url = f" → http://localhost:{host_port}" if host_port else ""
    return {"ok": code == 0, "msg": (out or err or f"{profile['name']} deployet") + url}
