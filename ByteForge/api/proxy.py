import datetime
import re

from api.config import PROXY_ROOT, CADDY_CONTAINER, load_config, save_config
from api.utils import run, slugify, docker_available, docker_status, docker_ports, container_exists
from api.docker_mgr import get_docker, docker_container_action


def _valid_domain(domain):
    if not domain or len(domain) > 253:
        return False
    if domain in ("localhost", "127.0.0.1"):
        return True
    return bool(re.fullmatch(r"(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", domain))


def _valid_target_host(host):
    return bool(re.fullmatch(r"[A-Za-z0-9_.:-]{1,253}", host or ""))


def _proxy_host_url(host):
    scheme = host.get("target_scheme") or "http"
    target_host = host.get("target_host") or "127.0.0.1"
    target_port = int(host.get("target_port") or 80)
    return f"{scheme}://{target_host}:{target_port}"


def _proxy_status():
    status = docker_status(CADDY_CONTAINER) if docker_available() else "docker unavailable"
    ports = docker_ports(CADDY_CONTAINER) if status == "running" else []
    return {"container": CADDY_CONTAINER, "status": status, "ports": ports}


def _proxy_targets():
    targets = []
    for container in get_docker():
        for port in docker_ports(container["name"]):
            targets.append({
                "name": container["name"],
                "image": container["image"],
                "host": "127.0.0.1",
                "port": port["host"],
                "container_port": port["container"],
            })
    return targets


def generate_caddyfile(hosts):
    lines = [
        "{",
        "    admin off",
        "}",
        "",
    ]
    for host in hosts:
        if not host.get("enabled", True):
            continue
        domain = host["domain"]
        site_addr = domain if host.get("ssl", True) else f"http://{domain}"
        tls_email = (host.get("tls_email") or "").strip()
        target = _proxy_host_url(host)
        lines.append(site_addr)
        lines.append("{")
        if host.get("ssl", True) and re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63}", tls_email):
            lines.append(f"    tls {tls_email}")
        lines.append(f"    reverse_proxy {target}")
        lines.append("}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def generate_nginx_config(hosts):
    blocks = []
    for host in hosts:
        if not host.get("enabled", True):
            continue
        domain = host["domain"]
        target = _proxy_host_url(host)
        blocks.append("\n".join([
            "server {",
            "    listen 80;",
            f"    server_name {domain};",
            "    location / {",
            f"        proxy_pass {target};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "    }",
            "}",
        ]))
    return "\n\n".join(blocks).strip() + "\n"


def save_proxy_files(hosts):
    PROXY_ROOT.mkdir(parents=True, exist_ok=True)
    caddyfile = PROXY_ROOT / "Caddyfile"
    nginx_conf = PROXY_ROOT / "nginx-byteforge.conf"
    caddyfile.write_text(generate_caddyfile(hosts))
    nginx_conf.write_text(generate_nginx_config(hosts))
    return caddyfile, nginx_conf


def get_proxy():
    config = load_config()
    hosts = config.get("proxy_hosts", [])
    caddyfile, nginx_conf = save_proxy_files(hosts)
    return {
        "hosts": hosts,
        "status": _proxy_status(),
        "targets": _proxy_targets() if docker_available() else [],
        "caddyfile": str(caddyfile),
        "nginx_config": str(nginx_conf),
        "npm": {
            "container": "byteforge-nginx-proxy-manager",
            "status": docker_status("byteforge-nginx-proxy-manager") if docker_available() else "docker unavailable",
            "url": "http://localhost:81",
        },
    }


def create_proxy_host(body):
    domain = (body.get("domain") or "").strip().lower()
    target_host = (body.get("target_host") or "127.0.0.1").strip()
    target_scheme = (body.get("target_scheme") or "http").strip().lower()
    try:
        target_port = int(body.get("target_port") or 80)
    except Exception:
        return {"ok": False, "msg": "Target port skal være et tal"}
    if not _valid_domain(domain):
        return {"ok": False, "msg": "Ugyldigt domæne. Brug fx app.example.com"}
    if target_scheme not in ("http", "https"):
        return {"ok": False, "msg": "Target scheme skal være http eller https"}
    if not _valid_target_host(target_host) or target_port < 1 or target_port > 65535:
        return {"ok": False, "msg": "Ugyldigt target host eller port"}

    config = load_config()
    hosts = [h for h in config.get("proxy_hosts", []) if h.get("domain") != domain]
    host = {
        "id": slugify(domain),
        "domain": domain,
        "target_scheme": target_scheme,
        "target_host": target_host,
        "target_port": target_port,
        "ssl": bool(body.get("ssl", True)),
        "tls_email": (body.get("tls_email") or "").strip(),
        "enabled": bool(body.get("enabled", True)),
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    hosts.append(host)
    config["proxy_hosts"] = hosts
    save_config(config)
    save_proxy_files(hosts)
    return {"ok": True, "host": host, "msg": f"Proxy host gemt: {domain}"}


def delete_proxy_host(body):
    host_id = body.get("id") or body.get("domain")
    config = load_config()
    before = len(config.get("proxy_hosts", []))
    config["proxy_hosts"] = [h for h in config.get("proxy_hosts", []) if h.get("id") != host_id and h.get("domain") != host_id]
    save_config(config)
    save_proxy_files(config["proxy_hosts"])
    return {"ok": len(config["proxy_hosts"]) < before, "msg": "Proxy host slettet" if len(config["proxy_hosts"]) < before else "Proxy host ikke fundet"}


def apply_proxy():
    config = load_config()
    hosts = config.get("proxy_hosts", [])
    caddyfile, _ = save_proxy_files(hosts)
    if not hosts:
        return {"ok": False, "msg": "Opret mindst én proxy host først"}
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig. Installer Docker før Caddy proxy startes."}

    data_dir = PROXY_ROOT / "caddy-data"
    config_dir = PROXY_ROOT / "caddy-config"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    if container_exists(CADDY_CONTAINER):
        out, err, code = run(["docker", "restart", CADDY_CONTAINER], timeout=30, shell=False)
        return {"ok": code == 0, "msg": out or err or "Caddy proxy genstartet"}

    cmd = [
        "docker", "run", "-d", "--name", CADDY_CONTAINER,
        "--label", "byteforge.proxy=true",
        "--restart", "unless-stopped",
        "-p", "80:80", "-p", "443:443", "-p", "443:443/udp",
        "-v", f"{caddyfile}:/etc/caddy/Caddyfile:ro",
        "-v", f"{data_dir}:/data",
        "-v", f"{config_dir}:/config",
        "caddy:2-alpine",
    ]
    out, err, code = run(cmd, timeout=300, shell=False)
    return {"ok": code == 0, "msg": out or err or "Caddy proxy startet på port 80/443"}


def proxy_action(body):
    action = body.get("action", "restart")
    if action not in ("start", "stop", "restart", "remove"):
        return {"ok": False, "msg": "Ukendt proxy handling"}
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig"}
    if action == "start" and not container_exists(CADDY_CONTAINER):
        return apply_proxy()
    return docker_container_action(CADDY_CONTAINER, action)


def deploy_nginx_proxy_manager():
    if not docker_available():
        return {"ok": False, "msg": "Docker er ikke tilgængelig"}
    container = "byteforge-nginx-proxy-manager"
    if container_exists(container):
        return {"ok": False, "msg": "Nginx Proxy Manager er allerede installeret på http://localhost:81"}
    data_path = PROXY_ROOT / "npm-data"
    letsencrypt_path = PROXY_ROOT / "npm-letsencrypt"
    data_path.mkdir(parents=True, exist_ok=True)
    letsencrypt_path.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "-d", "--name", container,
        "--label", "byteforge.proxy=true",
        "--restart", "unless-stopped",
        "-p", "81:81", "-p", "8088:80", "-p", "8443:443",
        "-v", f"{data_path}:/data",
        "-v", f"{letsencrypt_path}:/etc/letsencrypt",
        "jc21/nginx-proxy-manager:latest",
    ]
    out, err, code = run(cmd, timeout=300, shell=False)
    msg = out or err or "Nginx Proxy Manager installeret på http://localhost:81"
    return {"ok": code == 0, "msg": msg}
