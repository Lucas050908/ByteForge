import json
import re
import socket
import time
from pathlib import Path

from api.config import PLATFORM, load_config, save_config
from api.utils import run
from api.state import _UPTIME_HISTORY, _UPTIME_LOCK, _UPTIME_LATEST


def get_network_counters():
    if PLATFORM == "Linux":
        try:
            rows = Path("/proc/net/dev").read_text().splitlines()[2:]
            counters = []
            for row in rows:
                if ":" not in row:
                    continue
                iface, raw = row.split(":", 1)
                iface = iface.strip()
                parts = raw.split()
                if iface == "lo" or len(parts) < 16:
                    continue
                counters.append({"iface": iface, "rx": int(parts[0]), "tx": int(parts[8])})
            if counters:
                primary = max(counters, key=lambda item: item["rx"] + item["tx"])
                return {"iface": primary["iface"], "rx": primary["rx"], "tx": primary["tx"]}
        except Exception:
            pass
    if PLATFORM == "Darwin":
        out, _, _ = run("netstat -ibn | awk 'NR>1 && $1 != \"lo0\" {rx[$1]+=$7; tx[$1]+=$10} END {for (i in rx) print i, rx[i], tx[i]}'", shell=True)
        rows = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 3:
                try:
                    rows.append({"iface": parts[0], "rx": int(parts[1]), "tx": int(parts[2])})
                except Exception:
                    pass
        if rows:
            return max(rows, key=lambda item: item["rx"] + item["tx"])
    if PLATFORM == "Windows":
        out, _, _ = run("netstat -e", shell=True)
        numbers = [int(part) for part in re.findall(r"\b\d+\b", out)]
        if len(numbers) >= 2:
            return {"iface": "default", "rx": numbers[0], "tx": numbers[1]}
    return {"iface": "unknown", "rx": 0, "tx": 0}


def get_network():
    counters = get_network_counters()
    hostname = socket.gethostname()
    ip_addr = "?"
    gateway = "?"
    if PLATFORM == "Linux":
        ip_addr, _, _ = run("hostname -I 2>/dev/null | awk '{print $1}'")
        gateway, _, _ = run("ip route 2>/dev/null | awk '/default/ {print $3; exit}'")
    elif PLATFORM == "Darwin":
        ip_addr, _, _ = run("ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null")
        gateway, _, _ = run("route -n get default 2>/dev/null | awk '/gateway/ {print $2; exit}'")
    elif PLATFORM == "Windows":
        ip_out, _, _ = run("powershell -NoProfile -Command \"(Get-NetIPConfiguration | Where-Object {$_.IPv4DefaultGateway -ne $null} | Select-Object -First 1).IPv4Address.IPAddress\"", shell=True)
        gw_out, _, _ = run("powershell -NoProfile -Command \"(Get-NetIPConfiguration | Where-Object {$_.IPv4DefaultGateway -ne $null} | Select-Object -First 1).IPv4DefaultGateway.NextHop\"", shell=True)
        ip_addr, gateway = ip_out, gw_out
    return {
        "interface": counters["iface"],
        "hostname": hostname,
        "ip": ip_addr.strip() or "?",
        "gateway": gateway.strip() or "?",
        "dns": get_dns_servers(),
        "rx_total": counters["rx"],
        "tx_total": counters["tx"],
    }


def get_network_devices():
    out, _, _ = run("ip neigh show 2>/dev/null", shell=True, timeout=5)
    devices = []
    seen = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "lladdr" and parts[0] not in seen:
            ip, mac = parts[0], parts[4]
            seen.add(ip)
            state = parts[-1] if parts[-1] in ("REACHABLE","STALE","DELAY","PERMANENT") else "UNKNOWN"
            hostname, _, _ = run(f"getent hosts {ip} 2>/dev/null | awk '{{print $2}}'", shell=True, timeout=2)
            devices.append({"ip": ip, "mac": mac, "hostname": hostname.strip() or "—", "state": state})
    return sorted(devices, key=lambda d: [int(x) for x in d["ip"].split(".") if x.isdigit()])


def get_dns_servers():
    try:
        lines = Path("/etc/resolv.conf").read_text().splitlines()
        return [l.split()[1] for l in lines if l.startswith("nameserver") and len(l.split()) >= 2]
    except Exception:
        return []


def get_uptime_checks():
    checks = {}
    # Internet — ping Cloudflare DNS
    out, _, code = run("ping -c 1 -W 2 1.1.1.1 2>/dev/null", shell=True, timeout=5)
    m = re.search(r'time=(\d+\.?\d*)', out)
    checks["inet"] = {"up": code == 0, "latency_ms": round(float(m.group(1))) if m else None}
    # NFS service
    nfs_out, _, _ = run(
        "systemctl is-active nfs-server 2>/dev/null || systemctl is-active nfs-kernel-server 2>/dev/null",
        shell=True)
    checks["nfs"] = {"up": nfs_out.strip() == "active", "latency_ms": None}
    # Minecraft — TCP port 25565
    mc_up = False
    try:
        with socket.create_connection(("127.0.0.1", 25565), timeout=1):
            mc_up = True
    except Exception:
        pass
    checks["mc"] = {"up": mc_up, "latency_ms": None}
    return checks


def _uptime_collector():
    global _UPTIME_LATEST
    import api.state as _state
    while True:
        try:
            checks = get_uptime_checks()
            _state._UPTIME_LATEST = checks
            with _UPTIME_LOCK:
                for key in ("nfs", "inet"):
                    _UPTIME_HISTORY.setdefault(key, [])
                    _UPTIME_HISTORY[key].append(checks.get(key, {}).get("up", False))
                    if len(_UPTIME_HISTORY[key]) > 30:
                        _UPTIME_HISTORY[key].pop(0)
        except Exception:
            pass
        time.sleep(30)


def get_uptime_with_history():
    import api.state as _state
    with _UPTIME_LOCK:
        history = {k: list(v) for k, v in _UPTIME_HISTORY.items()}
    result = dict(_state._UPTIME_LATEST)
    for key in ("nfs", "inet"):
        if key in result:
            result[key]["history"] = history.get(key, [])
    return result


def webhook_save(url):
    cfg = load_config()
    cfg.setdefault("settings", {})["webhook_url"] = url
    save_config(cfg)
    return {"ok": True, "msg": "Webhook gemt"}


def webhook_test(url):
    if not url:
        return {"ok": False, "msg": "Ingen webhook URL"}
    import urllib.request as urlreq
    payload = json.dumps({"content": "⚡ **ByteForge** test alert! Forbindelsen virker.", "username": "ByteForge"}).encode()
    try:
        req = urlreq.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urlreq.urlopen(req, timeout=5) as resp:
            return {"ok": resp.status < 300, "msg": f"Alert sendt! (HTTP {resp.status})"}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:120]}


def webhook_get():
    cfg = load_config()
    return {"url": cfg.get("settings", {}).get("webhook_url", "")}
