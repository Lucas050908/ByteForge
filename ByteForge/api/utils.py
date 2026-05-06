import subprocess
import time

from api.config import PLATFORM


def run(cmd, timeout=10, shell=True):
    try:
        r = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as exc:
        return "", str(exc), 1


def slugify(value):
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return "-".join(part for part in clean.split("-") if part)[:48] or f"server-{int(time.time())}"


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


def docker_ports(container):
    out, _, code = run(["docker", "port", container], timeout=5, shell=False)
    if code != 0:
        return []
    ports = []
    for line in out.splitlines():
        if "->" not in line:
            continue
        container_port, host_addr = [part.strip() for part in line.split("->", 1)]
        host_port = host_addr.rsplit(":", 1)[-1]
        ports.append({"container": container_port, "host": host_port})
    return ports


def container_exists(container):
    _, _, code = run(["docker", "inspect", "--format={{.Id}}", container], timeout=5, shell=False)
    return code == 0
