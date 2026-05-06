import threading
from api.config import BASE_DIR

SESSION_COOKIE = "byteforge_session"
SESSION_TTL = 12 * 60 * 60
OLD_OWNER_ID = "lu" + "cas"
_SESSIONS = {}
_AUTH_LOCK = threading.Lock()

_METRICS_HISTORY = []
_METRICS_LOCK = threading.Lock()
_NET_LAST = None
_UPTIME_HISTORY = {"nfs": [], "inet": []}
_UPTIME_LOCK = threading.Lock()
_UPTIME_LATEST = {}

_INSTALL_LOGS: dict = {}  # app_id -> {lines, done, ok}

BACKUP_DIR = BASE_DIR / "backups"
BACKUP_JOBS_PATH = BASE_DIR / "backup_jobs.json"
