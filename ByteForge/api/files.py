import shutil
from pathlib import Path

from api.config import PUBLIC_ROOT, PRIVATE_ROOT, SHARED_ROOT, SERVER_ROOT, load_config


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
