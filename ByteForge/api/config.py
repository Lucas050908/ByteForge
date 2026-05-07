import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import threading
from pathlib import Path

PLATFORM = platform.system()  # 'Linux', 'Darwin', 'Windows'


def _is_admin():
    if hasattr(os, "geteuid"):
        return os.geteuid() == 0
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


PORT = int(os.environ.get("BYTEFORGE_PORT", "8080"))
DEFAULT_HOME = (
    "/opt/byteforge" if (_is_admin() and PLATFORM != "Windows")
    else str(Path.home() / ".byteforge")
)
BASE_DIR = Path(os.environ.get("BYTEFORGE_HOME", DEFAULT_HOME))
CONFIG_PATH = Path(os.environ.get("BYTEFORGE_CONFIG", str(BASE_DIR / "servers.json")))
FILES_ROOT = Path(os.environ.get("BYTEFORGE_FILES", str(BASE_DIR / "files")))
PUBLIC_ROOT = FILES_ROOT / "public"
PRIVATE_ROOT = FILES_ROOT / "private"
SERVER_ROOT = FILES_ROOT / "servers"
SHARED_ROOT = FILES_ROOT / "shared"
PROXY_ROOT = BASE_DIR / "proxy"
CADDY_CONTAINER = "byteforge-caddy"
STATIC_FILES = {
    "/byteforge-platform.css": "byteforge-platform.css",
    "/byteforge-platform.js": "byteforge-platform.js",
    "/byteforge-logo.png": "byteforge-logo.png",
    "/byteforge-icon.png": "byteforge-icon.png",
}


def ensure_dirs():
    for path in (BASE_DIR, FILES_ROOT, PUBLIC_ROOT, PRIVATE_ROOT, SERVER_ROOT, SHARED_ROOT, PROXY_ROOT):
        path.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config({"servers": default_servers(), "users": default_users(), "settings": default_settings(), "proxy_hosts": []})


def default_servers():
    return []


def default_users():
    return [
        {"id": "admin", "name": "Admin", "role": "owner", "access": ["*"]},
        {"id": "guest", "name": "Guest", "role": "viewer", "access": ["public"]},
    ]


def default_auth():
    initial_password = os.environ.get("BYTEFORGE_ADMIN_PASSWORD") or os.environ.get("BYTEFORGE_DEFAULT_PASSWORD") or ""
    salt, password_hash = hash_password(initial_password) if initial_password else ("", "")
    return {
        "enabled": True,
        "users": [{
            "id": "admin",
            "username": "ADMIN",
            "name": "Admin",
            "role": "owner",
            "password_salt": salt,
            "password_hash": password_hash,
            "totp_secret": "",
            "totp_enabled": False,
            "password_change_required": not bool(initial_password),
        }],
    }


def default_settings():
    return {"theme": "forge-dark", "language": "da", "background": "grid", "website_hosting": True}


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return salt, base64.b64encode(digest).decode()


def load_config():
    from api.state import OLD_OWNER_ID
    ensure_dirs()
    try:
        with CONFIG_PATH.open() as f:
            data = json.load(f)
    except Exception:
        data = {}
    data.setdefault("servers", default_servers())
    data.setdefault("users", default_users())
    data.setdefault("settings", default_settings())
    data.setdefault("proxy_hosts", [])
    if "auth" not in data:
        data["auth"] = default_auth()
        save_config(data)
    changed = False
    for server in data.get("servers", []):
        if str(server.get("owner", "")).lower() == OLD_OWNER_ID:
            server["owner"] = "admin"
            changed = True
    for user in data.get("users", []):
        if str(user.get("id", "")).lower() == OLD_OWNER_ID or str(user.get("name", "")).lower() == OLD_OWNER_ID:
            user["id"] = "admin"
            user["name"] = "Admin"
            changed = True
    for user in data.get("auth", {}).get("users", []):
        if str(user.get("username", "")).lower() == OLD_OWNER_ID or str(user.get("id", "")).lower() == OLD_OWNER_ID:
            salt = user.get("password_salt", "")
            _, default_hash = hash_password("byteforge", salt) if salt else ("", "")
            user["id"] = "admin"
            user["username"] = "ADMIN"
            user["name"] = "Admin"
            if salt and hmac.compare_digest(user.get("password_hash", ""), default_hash):
                user["password_salt"] = ""
                user["password_hash"] = ""
                user["password_change_required"] = True
            changed = True
    if changed:
        save_config(data)
    return data


def save_config(data):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(CONFIG_PATH)
