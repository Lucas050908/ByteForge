import datetime
import json
import shlex
from pathlib import Path

from api.state import BACKUP_DIR, BACKUP_JOBS_PATH
from api.utils import run, slugify


def load_backup_jobs():
    try:
        with BACKUP_JOBS_PATH.open() as f:
            return json.load(f)
    except Exception:
        return []


def save_backup_jobs(jobs):
    BACKUP_JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BACKUP_JOBS_PATH.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(jobs, f, indent=2)
    tmp.replace(BACKUP_JOBS_PATH)


def list_restore_points(job_name=""):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    points = []
    search = BACKUP_DIR / slugify(job_name) if job_name else BACKUP_DIR
    for p in sorted(search.rglob("*.tar.gz") if job_name else BACKUP_DIR.glob("**/*.tar.gz"), reverse=True):
        try:
            stat = p.stat()
            points.append({
                "name": p.name,
                "path": str(p),
                "job": p.parent.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 1),
                "created": int(stat.st_mtime),
            })
        except Exception:
            pass
    return points[:30]


def run_backup_job(job):
    src = job.get("src", "").strip()
    if not src or not Path(src).exists():
        return {"ok": False, "msg": f"Kilde ikke fundet: {src}"}
    job_dir = BACKUP_DIR / slugify(job["name"])
    job_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = job_dir / f"{slugify(job['name'])}_{ts}.tar.gz"
    out, err, code = run(
        f"tar -czf {shlex.quote(str(dest))} -C {shlex.quote(str(Path(src).parent))} {shlex.quote(Path(src).name)} 2>&1",
        timeout=300, shell=True
    )
    if code == 0:
        size_mb = round(dest.stat().st_size / (1024 * 1024), 1)
        # Update last run time in jobs
        jobs = load_backup_jobs()
        for j in jobs:
            if j.get("id") == job.get("id"):
                j["last_run"] = ts
                j["last_size_mb"] = size_mb
        save_backup_jobs(jobs)
        return {"ok": True, "msg": f"Backup fuldført: {dest.name} ({size_mb} MB)", "file": str(dest)}
    return {"ok": False, "msg": out or err or "Backup fejlede"}
