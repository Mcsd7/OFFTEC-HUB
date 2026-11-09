"""Real provider adapters and tightly scoped project editing for AI Coding."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .config import AI_CONFIG_PATH

PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta", "style": "gemini"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "style": "openai"},
    "openai": {"base_url": "https://api.openai.com/v1", "style": "openai"},
    "compatible": {"base_url": "", "style": "openai"},
}


def get_config():
    if not AI_CONFIG_PATH.is_file():
        return {"configured": False}
    try:
        raw = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
        configs = raw.get("providers") if isinstance(raw, dict) else None
        if configs:
            active = max(0, min(int(raw.get("active", 0)), len(configs) - 1))
            item = configs[active]
            return {"configured": True, "provider": item["provider"], "model": item["model"],
                    "base_url": item.get("base_url", ""), "key_set": bool(item.get("api_key")), "provider_count": len(configs),
                    "providers": [{"provider": entry["provider"], "model": entry["model"]} for entry in configs], "active": active}
        return {"configured": True, "provider": raw["provider"], "model": raw["model"],
                "base_url": raw.get("base_url", ""), "key_set": bool(raw.get("api_key")), "provider_count": 1,
                "providers": [{"provider": raw["provider"], "model": raw["model"]}], "active": 0}
    except (OSError, ValueError, KeyError):
        return {"configured": False}


def save_config(provider, model, api_key, base_url=""):
    if provider not in PROVIDERS:
        raise ValueError("Provedor não suportado.")
    model, api_key = model.strip(), api_key.strip()
    if not model or not api_key:
        raise ValueError("Informe o modelo e a chave de API.")
    if provider == "compatible" and not base_url.strip():
        raise ValueError("Informe a URL base da API compatível.")
    config = {"provider": provider, "model": model, "api_key": api_key,
              "base_url": (base_url.strip().rstrip("/") if provider == "compatible" else PROVIDERS[provider]["base_url"])}
    existing = []
    if AI_CONFIG_PATH.is_file():
        try:
            raw = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
            existing = raw.get("providers", []) if isinstance(raw, dict) else []
            if not existing and raw.get("api_key"):
                existing = [raw]
        except (OSError, ValueError):
            pass
    existing = [item for item in existing if not (item.get("provider") == provider and item.get("model") == model)]
    existing.append(config)
    AI_CONFIG_PATH.write_text(json.dumps({"providers": existing, "active": len(existing) - 1}), encoding="utf-8")
    try:
        AI_CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
    return get_config()


def select_config(index):
    raw = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
    if "providers" not in raw:
        if index != 0:
            raise ValueError("Provedor configurado não encontrado.")
        return get_config()
    if index < 0 or index >= len(raw["providers"]):
        raise ValueError("Provedor configurado não encontrado.")
    raw["active"] = index
    AI_CONFIG_PATH.write_text(json.dumps(raw), encoding="utf-8")
    try:
        AI_CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
    return get_config()


def _call(prompt):
    raw = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
    if "providers" in raw:
        config = raw["providers"][max(0, min(int(raw.get("active", 0)), len(raw["providers"]) - 1))]
    else:
        config = raw
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
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise RuntimeError(f"Provedor de IA retornou HTTP {exc.code}: {detail}") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Falha na chamada ao provedor de IA: {exc}") from exc
    if style == "gemini":
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        text = data["choices"][0]["message"]["content"]
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    result = json.loads(text)
    if not isinstance(result, dict) or not isinstance(result.get("files"), list):
        raise RuntimeError("A resposta da IA não contém a lista de arquivos esperada.")
    return result


def build_project(project: Path, request: str):
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
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return {"summary": str(result.get("summary", "")), "changed_files": [x[2] for x in changes], "file_count": len(changes)}
