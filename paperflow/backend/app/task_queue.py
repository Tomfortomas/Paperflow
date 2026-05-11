"""Lightweight task queue with cancellable / retriable / resumable tasks (PRD §8).

This module owns the in-memory representation of every long-running
backend job (report generation, R1 search, field map, comparison,
insight generation, Obsidian export). It tracks lifecycle (queued →
running → completed/failed/cancelled), exposes status via plain
:class:`AgentTask` snapshots, persists snapshots to disk so a backend
restart can reload "what was happening", and lets the API layer
cancel/retry a job by id.

The queue is intentionally cooperative: cancellation flips a
``threading.Event`` and the worker callable must check it. Existing
agent code already runs in short steps so this is a low-risk
contract.
"""

from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from app.models import AgentTask, AgentTaskKind


TaskCallable = Callable[["TaskHandle"], Optional[str]]
"""Worker signature.

The worker receives a :class:`TaskHandle` so it can publish progress and
check cancellation. The optional return value, if any, is a path to a
persisted result (stored in :attr:`AgentTask.result_path`).
"""


@dataclass
class TaskHandle:
    """Handed to worker callables — the public API to update a task."""

    task_id: str
    _queue: "TaskQueue"
    cancel_event: threading.Event = field(default_factory=threading.Event)

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def progress(self, value: float, message: str = "") -> None:
        self._queue._update(self.task_id, progress=value, message=message)

    def message(self, message: str) -> None:
        self._queue._update(self.task_id, message=message)


class TaskQueue:
    """In-memory + on-disk task store.

    Tasks are run on dedicated daemon threads — this gives us cancellation
    semantics without pulling in asyncio executors.
    """

    def __init__(self, store_dir: Path) -> None:
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, AgentTask] = {}
        self._handles: Dict[str, TaskHandle] = {}
        self._workers: Dict[str, TaskCallable] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.RLock()
        self._load_persisted_tasks()

    # ------------------------------------------------------------ persistence

    def _path(self, task_id: str) -> Path:
        return self.store_dir / f"{task_id}.json"

    def _load_persisted_tasks(self) -> None:
        for path in self.store_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            try:
                task = AgentTask.model_validate(data)
            except Exception:
                continue
            # Anything that was "running" before a restart is now stale —
            # mark as failed so the user can retry.
            if task.stage == "running":
                task.stage = "failed"
                task.error = "Backend restarted while task was running"
                task.finished_at = time.time()
            self._tasks[task.id] = task

    def _persist(self, task: AgentTask) -> None:
        self._path(task.id).write_text(
            json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------ public API

    def submit(
        self,
        worker: TaskCallable,
        *,
        kind: AgentTaskKind = AgentTaskKind.OTHER,
        paper_id: Optional[str] = None,
        message: str = "",
    ) -> AgentTask:
        task_id = uuid.uuid4().hex[:16]
        task = AgentTask(
            id=task_id,
            kind=kind,
            paper_id=paper_id,
            stage="queued",
            message=message,
            progress=0.0,
        )
        handle = TaskHandle(task_id=task_id, _queue=self)
        with self._lock:
            self._tasks[task_id] = task
            self._handles[task_id] = handle
            self._workers[task_id] = worker
            self._persist(task)
        thread = threading.Thread(target=self._run, args=(task_id,), daemon=True)
        with self._lock:
            self._threads[task_id] = thread
        thread.start()
        return task

    def _run(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks[task_id]
            worker = self._workers[task_id]
            handle = self._handles[task_id]
            task.stage = "running"
            task.started_at = time.time()
            task.message = task.message or "running"
            self._persist(task)
        try:
            result_path = worker(handle)
        except Exception as exc:
            self._update(
                task_id,
                stage="failed",
                error=str(exc) or exc.__class__.__name__,
                message="task failed",
                trace=traceback.format_exc(),
            )
            return
        if handle.is_cancelled():
            self._update(task_id, stage="cancelled", message="cancelled by user")
            return
        self._update(
            task_id,
            stage="completed",
            message="done",
            progress=1.0,
            result_path=Path(result_path) if result_path else None,
        )

    def get(self, task_id: str) -> Optional[AgentTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def list(self) -> List[AgentTask]:
        with self._lock:
            return list(self._tasks.values())

    def cancel(self, task_id: str) -> Optional[AgentTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            handle = self._handles.get(task_id)
        if task is None or handle is None:
            return None
        if task.stage in {"completed", "failed", "cancelled"}:
            return task
        handle.cancel_event.set()
        # Mark immediately so the UI can react even if the worker is
        # mid-step; the worker is expected to bail at the next progress
        # checkpoint.
        self._update(task_id, message="cancelling…")
        return self.get(task_id)

    def retry(self, task_id: str) -> Optional[AgentTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            worker = self._workers.get(task_id)
        if task is None or worker is None:
            return None
        if task.stage not in {"failed", "cancelled"}:
            return task  # nothing to retry
        # Reset state and resubmit; bump the retries counter.
        task.stage = "queued"
        task.error = None
        task.progress = 0.0
        task.retries += 1
        task.message = f"retry #{task.retries}"
        task.started_at = None
        task.finished_at = None
        self._persist(task)
        handle = TaskHandle(task_id=task.id, _queue=self)
        with self._lock:
            self._handles[task_id] = handle
        thread = threading.Thread(target=self._run, args=(task_id,), daemon=True)
        with self._lock:
            self._threads[task_id] = thread
        thread.start()
        return task

    # ------------------------------------------------------------ internals

    def _update(
        self,
        task_id: str,
        *,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        error: Optional[str] = None,
        result_path: Optional[Path] = None,
        trace: Optional[str] = None,  # unused but accepted for symmetry
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if stage is not None:
                task.stage = stage
                if stage in {"completed", "failed", "cancelled"}:
                    task.finished_at = time.time()
            if message is not None:
                task.message = message
            if progress is not None:
                task.progress = max(0.0, min(1.0, progress))
            if error is not None:
                task.error = error
            if result_path is not None:
                task.result_path = result_path
            self._persist(task)
