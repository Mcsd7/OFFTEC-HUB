"""Task status and process cancellation for isolated Codex runs."""
import asyncio
import threading
import uuid

from .tasks import run_blocking
from .. import codex_cli
from ..database import store

_tasks = {}


def start(project, prompt, test_only=False):
    task_id = uuid.uuid4().hex[:12]
    cancel_event = threading.Event()
    entry = {"task_id": task_id, "status": "running", "cancel_event": cancel_event, "result": None, "error": None}

    async def work():
        try:
            result = await run_blocking(codex_cli.run_task, project, prompt, True, test_only, cancel_event)
            entry["result"] = result
            entry["status"] = result["status"]
            store.record("codex", "smoke_test" if test_only else "exec", result["status"], {"run_id": result["run_id"], "workspace": result["workspace"], "changed_files": result["files"]})
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)[:1000]
            store.record("codex", "exec", "error", {"task_id": task_id, "error": type(exc).__name__})

    entry["task"] = asyncio.create_task(work())
    _tasks[task_id] = entry
    return task_id


def get(task_id):
    entry = _tasks.get(task_id)
    if not entry:
        return None
    status = "cancelling" if entry["cancel_event"].is_set() and entry["status"] == "running" else entry["status"]
    return {"task_id": task_id, "status": status, "result": entry["result"], "error": entry["error"]}


def cancel(task_id):
    entry = _tasks.get(task_id)
    if not entry:
        return None
    if entry["status"] == "running":
        entry["cancel_event"].set()
    return get(task_id)
