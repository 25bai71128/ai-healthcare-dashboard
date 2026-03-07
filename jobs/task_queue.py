"""Lightweight async task queue for background prediction/report jobs."""

from __future__ import annotations

import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any, Callable


class TaskQueue:
    """In-memory task queue with status tracking."""

    def __init__(self, workers: int = 2) -> None:
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self._tasks: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, Future] = {}
        self._lock = Lock()

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """Submit callable and return job id."""
        job_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "result": None,
                "error": None,
            }

        future = self.executor.submit(self._run_task, job_id, fn, *args, **kwargs)
        with self._lock:
            self._futures[job_id] = future
        return job_id

    def _run_task(self, job_id: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Execute task and update status."""
        with self._lock:
            self._tasks[job_id]["status"] = "running"

        try:
            result = fn(*args, **kwargs)
            with self._lock:
                self._tasks[job_id]["status"] = "completed"
                self._tasks[job_id]["result"] = result
        except Exception as exc:  # pragma: no cover - background failures
            with self._lock:
                self._tasks[job_id]["status"] = "failed"
                self._tasks[job_id]["error"] = f"{exc}\n{traceback.format_exc()}"

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return task status payload."""
        with self._lock:
            return self._tasks.get(job_id)

    def list_tasks(self, limit: int = 25) -> list[dict[str, Any]]:
        """List most recent tasks."""
        with self._lock:
            items = list(self._tasks.values())
        return sorted(items, key=lambda x: x["created_at"], reverse=True)[:limit]
