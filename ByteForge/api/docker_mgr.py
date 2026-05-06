from api.utils import run, docker_ports


def get_docker():
    out, _, _ = run("docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}' 2>/dev/null")
    containers = []
    for line in out.splitlines():
        if "|" in line:
            name, status, image = line.split("|", 2)
            containers.append({"name": name, "status": status, "image": image})
    return containers


def docker_container_action(container, action):
    if not container:
        return {"ok": False, "msg": "Ingen container angivet"}
    if action == "remove":
        out, err, code = run(["docker", "rm", "-f", container], timeout=15, shell=False)
    elif action in ("start", "stop", "restart"):
        out, err, code = run(["docker", action, container], timeout=30, shell=False)
    else:
        return {"ok": False, "msg": "Ukendt handling"}
    return {"ok": code == 0, "msg": out or err or f"{container} {action}"}
