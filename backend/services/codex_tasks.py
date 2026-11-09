"""Task status and process cancellation for isolated Codex runs."""
import asyncio
import threading
import uuid

from .tasks import run_blocking
from .. import codex_cli
from ..database import store

_tasks = {}


def start(project, prompt, test_only=False, method="auto"):
    task_id = uuid.uuid4().hex[:12]
    cancel_event = threading.Event()
    entry = {"task_id": task_id, "status": "running", "method": method, "cancel_event": cancel_event,
             "result": None, "error": None, "events": [], "stdout_tail": "", "stderr_tail": ""}

    def on_update(update):
        if "final" in update:
            entry["result"] = update["final"]
            return
        if update.get("event"):
            entry["events"].append(update["event"])
            entry["events"] = entry["events"][-100:]
        entry["stdout_tail"] = update.get("stdout_tail", entry["stdout_tail"])
        entry["stderr_tail"] = update.get("stderr_tail", entry["stderr_tail"])
        entry["method"] = update.get("method", entry["method"])

    async def work():
        try:
            result = await run_blocking(codex_cli.run_task, project, prompt, True, test_only, cancel_event, method, on_update)
            entry["result"] = result
            entry["status"] = result["status"]
            store.record("codex", "smoke_test" if test_only else "exec", result["status"], {"run_id": result["run_id"], "workspace": result["workspace"], "changed_files": result["files"]})
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = codex_cli._redact(str(exc))[:2000]
            store.record("codex", "exec", "error", {"task_id": task_id, "error": type(exc).__name__})

    entry["task"] = asyncio.create_task(work())
    _tasks[task_id] = entry
    return task_id


def get(task_id):
    entry = _tasks.get(task_id)
    if not entry:
        return None
    status = "cancelling" if entry["cancel_event"].is_set() and entry["status"] == "running" else entry["status"]
    return {"task_id": task_id, "status": status, "method": entry["method"], "result": entry["result"],
            "error": entry["error"], "events": list(entry["events"]),
            "stdout_tail": entry["stdout_tail"], "stderr_tail": entry["stderr_tail"]}


def cancel(task_id):
    entry = _tasks.get(task_id)
    if not entry:
        return None
    if entry["status"] == "running":
        entry["cancel_event"].set()
    return get(task_id)
