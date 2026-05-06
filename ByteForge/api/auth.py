import base64
import hashlib
import hmac
import re
import secrets
import time

from api.config import hash_password, load_config, save_config
from api.state import SESSION_COOKIE, SESSION_TTL, _SESSIONS, _AUTH_LOCK


def _parse_cookies(header):
    cookies = {}
    for part in (header or "").split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            cookies[key] = value
    return cookies


def _verify_password(user, password):
    salt = user.get("password_salt", "")
    expected = user.get("password_hash", "")
    if not salt or not expected:
        return False
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected)


def _b32_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _totp_code(secret, timestep=None):
    timestep = int(time.time() // 30) if timestep is None else timestep
    padded = secret.upper() + ("=" * ((8 - len(secret) % 8) % 8))
    key = base64.b32decode(padded)
    msg = timestep.to_bytes(8, "big")
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = int.from_bytes(digest[offset:offset + 4], "big") & 0x7fffffff
    return f"{code % 1_000_000:06d}"


def _verify_totp(secret, code):
    code = re.sub(r"\s+", "", str(code or ""))
    if not re.fullmatch(r"\d{6}", code):
        return False
    now_step = int(time.time() // 30)
    return any(hmac.compare_digest(_totp_code(secret, now_step + drift), code) for drift in (-1, 0, 1))


def _find_auth_user(username):
    auth = load_config().get("auth", {})
    for user in auth.get("users", []):
        if user.get("username", "").lower() == (username or "").lower():
            return user
    return None


def _public_user(user):
    if not user:
        return None
    return {
        "id": user.get("id"),
        "username": user.get("username"),
        "name": user.get("name"),
        "role": user.get("role"),
        "totp_enabled": bool(user.get("totp_enabled")),
        "password_change_required": bool(user.get("password_change_required")),
    }


def _session_user(handler):
    token = _parse_cookies(handler.headers.get("Cookie")).get(SESSION_COOKIE)
    if not token:
        return None
    now = time.time()
    with _AUTH_LOCK:
        session = _SESSIONS.get(token)
        if not session or session["expires"] < now:
            _SESSIONS.pop(token, None)
            return None
        session["expires"] = now + SESSION_TTL
        username = session["username"]
    return _find_auth_user(username)


def auth_enabled():
    return bool(load_config().get("auth", {}).get("enabled", True))


def auth_status(handler):
    if not auth_enabled():
        return {"authenticated": True, "auth_enabled": False, "user": {"username": "local", "name": "Local"}}
    user = _session_user(handler)
    auth = load_config().get("auth", {})
    setup_required = any(not item.get("password_hash") for item in auth.get("users", []))
    return {"authenticated": bool(user), "auth_enabled": True, "setup_required": setup_required, "user": _public_user(user)}


def auth_setup(body):
    config = load_config()
    auth = config.get("auth", {})
    users = auth.get("users", [])
    if not any(not item.get("password_hash") for item in users):
        return {"ok": False, "msg": "Admin password is already configured"}
    password = body.get("password") or ""
    confirm = body.get("confirm") or ""
    if len(password) < 8:
        return {"ok": False, "msg": "Admin password must be at least 8 characters"}
    if password != confirm:
        return {"ok": False, "msg": "Passwords do not match"}
    for item in users:
        if not item.get("password_hash"):
            salt, password_hash = hash_password(password)
            item["username"] = "ADMIN"
            item["name"] = "Admin"
            item["password_salt"] = salt
            item["password_hash"] = password_hash
            item["password_change_required"] = False
            break
    save_config(config)
    return {"ok": True, "msg": "Admin password configured. You can log in now."}


def auth_login(body):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    otp = body.get("otp") or ""
    user = _find_auth_user(username)
    if not user or not _verify_password(user, password):
        return None, {"ok": False, "msg": "Forkert brugernavn eller adgangskode"}
    if user.get("totp_enabled") and not _verify_totp(user.get("totp_secret", ""), otp):
        return None, {"ok": False, "requires_2fa": True, "msg": "Indtast gyldig 2FA kode"}
    token = secrets.token_urlsafe(32)
    with _AUTH_LOCK:
        _SESSIONS[token] = {"username": user["username"], "expires": time.time() + SESSION_TTL}
    return token, {"ok": True, "user": _public_user(user), "msg": "Logget ind"}


def auth_logout(handler):
    token = _parse_cookies(handler.headers.get("Cookie")).get(SESSION_COOKIE)
    with _AUTH_LOCK:
        _SESSIONS.pop(token, None)
    return {"ok": True, "msg": "Logget ud"}


def auth_change_password(handler, body):
    user = _session_user(handler)
    if not user:
        return {"ok": False, "msg": "Ikke logget ind"}
    current = body.get("current") or ""
    new_password = body.get("new_password") or ""
    if not _verify_password(user, current):
        return {"ok": False, "msg": "Nuværende adgangskode er forkert"}
    if len(new_password) < 8:
        return {"ok": False, "msg": "Ny adgangskode skal være mindst 8 tegn"}
    config = load_config()
    for item in config.get("auth", {}).get("users", []):
        if item.get("username") == user.get("username"):
            salt, password_hash = hash_password(new_password)
            item["password_salt"] = salt
            item["password_hash"] = password_hash
            item["password_change_required"] = False
            break
    save_config(config)
    return {"ok": True, "msg": "Adgangskode opdateret"}


def auth_2fa_setup(handler):
    user = _session_user(handler)
    if not user:
        return {"ok": False, "msg": "Ikke logget ind"}
    config = load_config()
    secret = _b32_secret()
    for item in config.get("auth", {}).get("users", []):
        if item.get("username") == user.get("username"):
            item["totp_pending_secret"] = secret
            break
    save_config(config)
    label = f"ByteForge:{user.get('username')}"
    uri = f"otpauth://totp/{label}?secret={secret}&issuer=ByteForge&digits=6&period=30"
    return {"ok": True, "secret": secret, "otpauth": uri}


def auth_2fa_enable(handler, body):
    user = _session_user(handler)
    if not user:
        return {"ok": False, "msg": "Ikke logget ind"}
    config = load_config()
    for item in config.get("auth", {}).get("users", []):
        if item.get("username") == user.get("username"):
            secret = item.get("totp_pending_secret") or item.get("totp_secret")
            if not secret or not _verify_totp(secret, body.get("otp")):
                return {"ok": False, "msg": "Ugyldig 2FA kode"}
            item["totp_secret"] = secret
            item["totp_enabled"] = True
            item.pop("totp_pending_secret", None)
            save_config(config)
            return {"ok": True, "msg": "2FA er aktiveret"}
    return {"ok": False, "msg": "Bruger ikke fundet"}
