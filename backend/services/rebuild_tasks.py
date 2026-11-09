"""In-memory lifecycle for long-running APK rebuild workspaces."""
import asyncio
import threading
import uuid

from .tasks import run_blocking
from .. import apk_rebuild
from ..database import store
from ..core.events import events

_tasks = {}


def start(plan_id, request, allow_build=False):
    task_id = uuid.uuid4().hex[:12]
    cancel_event = threading.Event()
    entry = {"task_id": task_id, "status": "running", "cancel_event": cancel_event, "result": None, "error": None, "task": None}

    async def work():
        try:
            entry["result"] = await run_blocking(apk_rebuild.apply_plan, plan_id, request, True, allow_build, cancel_event)
            entry["status"] = "completed"
            store.record("apk_rebuild", "apply", "success", {"task_id": task_id, "workspace": entry["result"]["workspace"], "changed_files": entry["result"]["changes"]["changed_files"], "build": entry["result"]["build"]})
            await events.publish({"type": "progress", "task_id": task_id, "message": "Workspace e validação concluídos"})
        except InterruptedError as exc:
            entry["status"] = "cancelled"
            entry["error"] = str(exc)
            store.record("apk_rebuild", "apply", "cancelled", {"task_id": task_id})
            await events.publish({"type": "error", "task_id": task_id, "message": "Reconstrução cancelada"})
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = type(exc).__name__
            store.record("apk_rebuild", "apply", "error", {"task_id": task_id, "error": type(exc).__name__})
            await events.publish({"type": "error", "task_id": task_id, "message": "Falha na reconstrução assistida"})

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
