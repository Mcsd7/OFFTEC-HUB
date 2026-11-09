"""Persistent, real Codex CLI chat conversations over isolated task workspaces."""
import asyncio
from pathlib import Path

from ..database import store
from . import codex_tasks


def start(conversation_id, prompt, source, method, test_only):
    conversation = store.codex_conversation_get(conversation_id)
    if not conversation:
        raise KeyError("Conversa Codex não encontrada.")
    context = []
    for message in conversation["messages"][-20:-1]:
        if message["role"] in {"user", "assistant"}:
            context.append(f"{message['role'].upper()}: {message['content'][:6000]}")
    full_prompt = ("Você é o Codex CLI real. Continue esta conversa mantendo o contexto. "
                   "Responda em português quando apropriado. Não afirme que editou arquivos sem verificar a execução.\n\n"
                   + ("Histórico recente:\n" + "\n\n".join(context) + "\n\n" if context else "")
                   + "Mensagem atual:\n" + prompt)
    task_id = codex_tasks.start(Path(source), full_prompt, test_only=test_only, method=method)

    async def persist_result():
        while True:
            await asyncio.sleep(.35)
            state = codex_tasks.get(task_id)
            if not state or state["status"] in {"running", "cancelling"}:
                continue
            result = state.get("result") or {}
            if state["status"] == "success":
                response = result.get("response") or "Codex concluiu sem uma mensagem final."
                store.codex_message_add(conversation_id, "assistant", response,
                    {"method": state.get("method"), "files": result.get("files", []),
                     "workspace": result.get("workspace"), "events": result.get("events", [])[-20:]})
                workspace = result.get("workspace")
                if workspace:
                    store.codex_conversation_update_workspace(conversation_id, workspace, state.get("method") or method)
            else:
                store.codex_message_add(conversation_id, "assistant",
                    state.get("error") or f"Execução Codex: {state['status']}.",
                    {"status": state["status"], "method": state.get("method"),
                     "stderr": state.get("stderr_tail", "")[-3000:]})
            return

    asyncio.create_task(persist_result())
    return task_id
