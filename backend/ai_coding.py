"""Real provider adapters and tightly scoped project editing for AI Coding."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .config import AI_CONFIG_PATH
from . import providers as provider_store

PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta", "style": "gemini"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "style": "openai"},
    "openai": {"base_url": "https://api.openai.com/v1", "style": "openai"},
    "compatible": {"base_url": "", "style": "openai"},
}


def get_config():
    try:
        return provider_store.status()
    except (OSError, ValueError, KeyError, TypeError):
        return {"configured": False, "providers": [], "provider_count": 0, "default_id": None}


def save_config(provider, model, api_key, base_url=""):
    return provider_store.save(provider.title(), provider, model, api_key, base_url)


def select_config(index):
    data = provider_store._read()
    if index < 0 or index >= len(data["providers"]):
        raise ValueError("Provedor configurado não encontrado.")
    return provider_store.select(data["providers"][index]["id"])


def _call(prompt):
    config = provider_store.get_secret()
    provider, model, key = config["provider"], config["model"], config["api_key"]
    style = PROVIDERS[provider]["style"]
    if style == "gemini":
        url = f"{config['base_url']}/models/{model}:generateContent"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    else:
        url = config["base_url"].rstrip("/") + "/chat/completions"
        payload = {"model": model, "temperature": 0.1, "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": "Return only JSON: {\"summary\":string,\"files\":[{\"path\":string,\"content\":string}]}. Paths must be relative."}, {"role": "user", "content": prompt}]}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Autenticação rejeitada pelo provedor (401/403). Verifique a API Key e as permissões.") from None
        if exc.code == 404:
            raise RuntimeError("Modelo ou endpoint não encontrado (404). Verifique o modelo e a Base URL.") from None
        raise RuntimeError(f"Provedor de IA retornou HTTP {exc.code}.") from None
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Falha na chamada ao provedor de IA: {type(exc).__name__}.") from None
    if style == "gemini":
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        text = data["choices"][0]["message"]["content"]
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    result = json.loads(text)
    if not isinstance(result, dict) or not isinstance(result.get("files"), list):
        raise RuntimeError("A resposta da IA não contém a lista de arquivos esperada.")
    return result


def build_project(project: Path, request: str, cancel_event=None):
    files = []
    ignored = {".git", ".gradle", "build", "node_modules", ".venv", "venv", "__pycache__", "dist", "target"}
    for path in sorted(project.rglob("*")):
        if not path.is_file() or path.is_symlink() or any(part in ignored for part in path.relative_to(project).parts):
            continue
        if path.stat().st_size > 100_000 or len(files) >= 120:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        files.append({"path": path.relative_to(project).as_posix(), "content": content})
    context = json.dumps(files, ensure_ascii=False)
    if len(context) > 150_000:
        context = context[:150_000] + "\n[CONTEXTO TRUNCADO]"
    prompt = f"Tarefa: {request}\n\nArquivos atuais do projeto (JSON):\n{context}\n\nRetorne JSON com summary e files. Para cada arquivo a criar ou alterar, inclua o conteúdo completo. Não altere arquivos de configuração de execução para executar comandos externos."
    result = _call(prompt)
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Operação cancelada antes de gravar qualquer arquivo no workspace.")
    changes = []
    if len(result["files"]) > 40:
        raise RuntimeError("A IA propôs mais de 40 arquivos; nenhuma alteração foi aplicada.")
    for item in result["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
            raise RuntimeError("A IA retornou uma alteração de arquivo inválida.")
        rel = Path(item["path"])
        if rel.is_absolute() or not rel.parts or any(p in {"..", "."} for p in rel.parts) or len(item["content"]) > 500_000:
            raise RuntimeError(f"Caminho/conteúdo não permitido: {item['path'][:120]}")
        dest = (project / rel).resolve()
        if project not in dest.parents or any(parent.is_symlink() for parent in [project / rel, *(project / rel).parents] if parent != project):
            raise RuntimeError(f"Arquivo sai do projeto selecionado: {item['path']}")
        changes.append((dest, item["content"], rel.as_posix()))
    for dest, content, relative in changes:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Operação cancelada; workspace descartável contém somente alterações parciais.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return {"summary": str(result.get("summary", "")), "changed_files": [x[2] for x in changes], "file_count": len(changes)}
