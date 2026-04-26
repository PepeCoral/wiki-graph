import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import config

JOBS_FILE: Path = config.BASE_DIR / "data" / "jobs.json"
JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)

_LOCK = threading.Lock()

def _read() -> Dict[str, dict]:
    try:
        if JOBS_FILE.exists():
            return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write(jobs: Dict[str, dict]) -> None:
    tmp = JOBS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    tmp.replace(JOBS_FILE)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False

def reconcile() -> None:
    with _LOCK:
        jobs = _read()
        changed = False
        for job in jobs.values():
            if job["status"] == "running":
                pid = job.get("pid", -1)
                if not _pid_alive(pid):
                    job["status"] = "interrupted"
                    job["message"] = "Interrupted — process ended unexpectedly"
                    job["ended_at"] = time.time()
                    changed = True
        if changed:
            _write(jobs)


def start_job(job_id: str, label: str) -> None:
    with _LOCK:
        jobs = _read()
        jobs[job_id] = {
            "id":         job_id,
            "label":      label,
            "status":     "running",
            "message":    "Starting…",
            "error":      None,
            "started_at": time.time(),
            "ended_at":   None,
            "pid":        os.getpid(),
        }
        _write(jobs)


def update_job(job_id: str, message: str) -> None:
    with _LOCK:
        jobs = _read()
        if job_id in jobs:
            jobs[job_id]["message"] = message
            _write(jobs)


def finish_job(job_id: str, message: str = "Completed successfully") -> None:
    with _LOCK:
        jobs = _read()
        if job_id in jobs:
            jobs[job_id].update(
                status="done",
                message=message,
                ended_at=time.time(),
            )
            _write(jobs)


def fail_job(job_id: str, error: str) -> None:
    with _LOCK:
        jobs = _read()
        if job_id in jobs:
            jobs[job_id].update(
                status="error",
                message=f"Failed: {error}",
                error=error,
                ended_at=time.time(),
            )
            _write(jobs)


def get_job(job_id: str) -> Optional[dict]:
    return _read().get(job_id)


def get_all() -> List[dict]:
    jobs = _read()
    return sorted(jobs.values(), key=lambda j: j.get("started_at", 0), reverse=True)


def clear_job(job_id: str) -> None:
    with _LOCK:
        jobs = _read()
        jobs.pop(job_id, None)
        _write(jobs)


def clear_finished() -> None:
    with _LOCK:
        jobs = _read()
        jobs = {k: v for k, v in jobs.items() if v["status"] == "running"}
        _write(jobs)


def has_running() -> bool:
    return any(j["status"] == "running" for j in _read().values())