"""Cooperative cancellation for OFFTEC AI generations."""
import asyncio
import threading
import uuid

from .tasks import run_blocking
from .. import main

_tasks = {}


def start(conversation_id, message):
    task_id = uuid.uuid4().hex[:12]
    cancel_event = threading.Event()
    entry = {"task_id": task_id, "conversation_id": conversation_id, "status": "running", "cancel_event": cancel_event, "result": None, "error": None}

    async def work():
        try:
            entry["result"] = await main._chat_continue(conversation_id, cancel_event)
            entry["status"] = "cancelled" if cancel_event.is_set() else "completed"
        except Exception as exc:
            entry["status"] = "error"
            entry["error"] = type(exc).__name__
            main.store.message_add(conversation_id, "assistant", f"Falha na geração: {type(exc).__name__}.")

    entry["task"] = asyncio.create_task(work())
    _tasks[task_id] = entry
    return task_id


def get(task_id):
    entry = _tasks.get(task_id)
    if not entry:
        return None
    status = "cancelling" if entry["cancel_event"].is_set() and entry["status"] == "running" else entry["status"]
    return {"task_id": task_id, "conversation_id": entry["conversation_id"], "status": status,
            "result": entry["result"], "error": entry["error"]}


def cancel(task_id):
    entry = _tasks.get(task_id)
    if not entry:
        return None
    if entry["status"] == "running":
        entry["cancel_event"].set()
    return get(task_id)
