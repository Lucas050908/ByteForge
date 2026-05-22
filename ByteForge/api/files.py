import os
import shutil
from pathlib import Path

from api.config import PUBLIC_ROOT, PRIVATE_ROOT, SHARED_ROOT, SERVER_ROOT, load_config

# Resolve the real user's home even when running under sudo
def _real_home():
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        import pwd
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except Exception:
            pass
    return Path.home()

HOME_ROOT = _real_home()


def safe_path(scope, rel=""):
    rel = str(rel or "")
    roots = {
        "home":    HOME_ROOT,
        "public":  PUBLIC_ROOT,
        "private": PRIVATE_ROOT,
        "shared":  SHARED_ROOT,
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


def list_files(scope, rel="", show_hidden=False):
    _, target = safe_path(scope, rel)
    if target.exists() and not target.is_dir():
        return {"path": rel, "items": []}
    try:
        target.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        return {"path": rel, "items": []}
    if not target.is_dir():
        return {"path": rel, "items": []}
    items = []
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return {"path": rel, "items": []}
    for entry in entries:
        if not show_hidden and entry.name.startswith("."):
            continue
        try:
            stat = entry.stat()
        except (OSError, PermissionError):
            continue
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
    try:
        for path in root.rglob("*"):
            try:
                if query.lower() in path.name.lower():
                    matches.append({"path": str(path.relative_to(root)), "type": "folder" if path.is_dir() else "file"})
            except (OSError, PermissionError):
                continue
            if len(matches) >= 100:
                break
    except (OSError, PermissionError):
        pass
    return matches


def file_action(body):
    action = body.get("action")
    scope = body.get("scope", "public")
    path = body.get("path", "")
    root, target = safe_path(scope, path)
    if action == "mkdir":
        target.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "msg": "Mappe oprettet"}
    if action == "delete":
        if target == root:
            return {"ok": False, "msg": "Kan ikke slette storage-roden"}
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return {"ok": True, "msg": "Slettet"}
    if action == "rename":
        if target == root:
            return {"ok": False, "msg": "Kan ikke omdøbe storage-roden"}
        if not target.exists():
            return {"ok": False, "msg": "Fil ikke fundet"}
        new_name = body.get("new_name", "").strip()
        if not new_name or "/" in new_name or "\\" in new_name:
            return {"ok": False, "msg": "Ugyldigt navn"}
        _, dest = safe_path(scope, str(Path(path).parent / new_name))
        if dest.exists():
            return {"ok": False, "msg": f"{new_name} eksisterer allerede"}
        target.rename(dest)
        return {"ok": True, "msg": f"Omdøbt til {new_name}"}
    if action == "move":
        if target == root:
            return {"ok": False, "msg": "Kan ikke flytte storage-roden"}
        if not target.exists():
            return {"ok": False, "msg": "Fil ikke fundet"}
        _, dest = safe_path(scope, body.get("dest", ""))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(dest))
        return {"ok": True, "msg": "Flyttet"}
    if action == "search":
        return {"ok": True, "matches": search_files(scope, body.get("query", ""))}
    return {"ok": False, "msg": "Ukendt filhandling"}
