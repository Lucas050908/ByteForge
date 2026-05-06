import os
import shutil
import time
from pathlib import Path

import api.state as _state
from api.config import PORT, PLATFORM, BASE_DIR, load_config
from api.system import get_system, _is_admin
from api.network import get_network_counters
from api.state import _METRICS_HISTORY, _METRICS_LOCK, _NET_LAST
from api.utils import run, docker_available


def _metrics_collector():
    while True:
        try:
            s = get_system()
            net = get_network_counters()
            now = int(time.time())
            rx_bps = tx_bps = 0
            if _state._NET_LAST and net["rx"] >= _state._NET_LAST["rx"] and net["tx"] >= _state._NET_LAST["tx"]:
                elapsed = max(1, now - _state._NET_LAST["ts"])
                rx_bps = round((net["rx"] - _state._NET_LAST["rx"]) / elapsed)
                tx_bps = round((net["tx"] - _state._NET_LAST["tx"]) / elapsed)
            _state._NET_LAST = {"ts": now, "rx": net["rx"], "tx": net["tx"]}
            entry = {
                "ts": now,
                "cpu": s["cpu"],
                "ram": s["ram_pct"],
                "temp": s["temp"] if isinstance(s["temp"], (int, float)) else 0,
                "net_iface": net["iface"],
                "rx_bps": rx_bps,
                "tx_bps": tx_bps,
            }
            with _METRICS_LOCK:
                _METRICS_HISTORY.append(entry)
                if len(_METRICS_HISTORY) > 60:
                    _METRICS_HISTORY.pop(0)
        except Exception:
            pass
        time.sleep(5)


def setup_status():
    svc_path = Path("/etc/systemd/system/byteforge.service")
    return {
        "docker_ok": docker_available(),
        "service_ok": svc_path.exists(),
        "port": PORT,
        "base_dir": str(BASE_DIR),
    }


def install_docker_system():
    if docker_available():
        return {"ok": True, "msg": "Docker er allerede installeret"}
    if PLATFORM == "Windows":
        return {"ok": False, "msg": "Download Docker Desktop fra https://www.docker.com/products/docker-desktop og genstart ByteForge."}
    if PLATFORM == "Darwin":
        if not shutil.which("brew"):
            return {"ok": False, "msg": "Homebrew er ikke installeret. Installer Docker Desktop manuelt eller installer Homebrew først."}
        out, err, code = run("brew install --cask docker 2>&1", timeout=300, shell=True)
        return {"ok": code == 0, "msg": (out or err or "Docker installeret via Homebrew. Start Docker.app manuelt.")[-2000:]}
    if not _is_admin():
        return {
            "ok": False,
            "msg": (
                "Docker-installation kræver superuser/root. Stop ByteForge og start den med sudo, "
                "eller installer Docker i terminalen med: curl -fsSL https://get.docker.com | sudo sh"
            ),
        }
    distro_out, _, _ = run("cat /etc/os-release 2>/dev/null")
    distro = ""
    for line in distro_out.splitlines():
        if line.startswith("ID="):
            distro = line.split("=", 1)[1].strip().strip('"').lower()
    if distro in ("arch", "manjaro", "endeavouros", "garuda"):
        out, err, code = run("pacman -Sy --noconfirm docker && systemctl enable --now docker", timeout=300, shell=True)
    elif distro in ("ubuntu", "debian", "linuxmint", "pop"):
        out, err, code = run("apt-get update -qq && apt-get install -y docker.io && systemctl enable --now docker", timeout=300, shell=True)
    elif distro in ("fedora", "rhel", "centos", "rocky"):
        out, err, code = run("dnf install -y docker && systemctl enable --now docker", timeout=300, shell=True)
    else:
        out, err, code = run("curl -fsSL https://get.docker.com | sh && systemctl enable --now docker", timeout=300, shell=True)
    return {"ok": code == 0, "msg": (out or err or "Docker installeret")[-2000:]}


def install_service_system():
    script_path = Path(__file__).resolve().parent.parent / "byteforge-server.py"
    python_path = shutil.which("python3") or shutil.which("python") or "python3"

    if PLATFORM == "Linux":
        admin_password = os.environ.get("BYTEFORGE_ADMIN_PASSWORD", "")
        unit = "\n".join([
            "[Unit]", "Description=ByteForge Platform", "After=network.target docker.service", "Wants=docker.service",
            "", "[Service]", "Type=simple",
            f"ExecStart={python_path} {script_path}", "Restart=always", "RestartSec=5",
            f"Environment=BYTEFORGE_PORT={PORT}",
            f"Environment=BYTEFORGE_ADMIN_PASSWORD={admin_password}" if admin_password else "",
            "", "[Install]", "WantedBy=multi-user.target", "",
        ])
        try:
            Path("/etc/systemd/system/byteforge.service").write_text(unit)
            run("systemctl daemon-reload && systemctl enable --now byteforge", timeout=20, shell=True)
            return {"ok": True, "msg": f"ByteForge installeret som systemd service på port {PORT}. Starter automatisk ved boot."}
        except Exception as exc:
            return {"ok": False, "msg": str(exc)}

    if PLATFORM == "Darwin":
        admin_password = os.environ.get("BYTEFORGE_ADMIN_PASSWORD", "")
        plist_path = Path("/Library/LaunchDaemons/com.byteforge.server.plist")
        env_lines = [f"  <dict><key>BYTEFORGE_PORT</key><string>{PORT}</string>"]
        if admin_password:
            env_lines.append(f"<key>BYTEFORGE_ADMIN_PASSWORD</key><string>{admin_password}</string>")
        env_lines.append("</dict>")
        plist = "\n".join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0"><dict>',
            "  <key>Label</key><string>com.byteforge.server</string>",
            "  <key>ProgramArguments</key>",
            f"  <array><string>{python_path}</string><string>{script_path}</string></array>",
            "  <key>EnvironmentVariables</key>",
            "".join(env_lines),
            "  <key>RunAtLoad</key><true/>",
            "  <key>KeepAlive</key><true/>",
            "</dict></plist>",
        ])
        try:
            plist_path.write_text(plist)
            run(f"launchctl load -w {plist_path}", timeout=10, shell=True)
            return {"ok": True, "msg": f"ByteForge installeret som LaunchDaemon på port {PORT}. Starter ved boot."}
        except Exception as exc:
            return {"ok": False, "msg": str(exc)}

    if PLATFORM == "Windows":
        try:
            admin_password = os.environ.get("BYTEFORGE_ADMIN_PASSWORD", "")
            bat_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "ByteForge"
            bat_dir.mkdir(exist_ok=True)
            bat_path = bat_dir / "start.bat"
            lines = ["@echo off", f"set BYTEFORGE_PORT={PORT}"]
            if admin_password:
                lines.append(f"set BYTEFORGE_ADMIN_PASSWORD={admin_password}")
            lines.append(f'"{python_path}" "{script_path}"')
            bat_path.write_text("\n".join(lines) + "\n")
            task_cmd = f'schtasks /create /tn "ByteForge" /tr "{bat_path}" /sc onstart /ru SYSTEM /f'
            out, err, code = run(task_cmd, timeout=15, shell=True)
            return {"ok": code == 0, "msg": out or err or "ByteForge tilføjet til Windows Task Scheduler. Starter ved login."}
        except Exception as exc:
            return {"ok": False, "msg": str(exc)}

    return {"ok": False, "msg": f"Service installation ikke understøttet på {PLATFORM}"}
