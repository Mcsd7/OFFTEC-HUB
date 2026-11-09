"""Private, atomic storage and connectivity checks for AI providers."""
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .config import AI_CONFIG_PATH

DEFAULTS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "compatible": "",
}
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$")


def validate(provider, model, base_url=""):
    if provider not in DEFAULTS:
        raise ValueError("Provedor não suportado.")
    model = model.strip()
    if not MODEL_ID.fullmatch(model):
        raise ValueError("ID do modelo inválido. Use letras, números, ponto, _, :, / ou hífen.")
    if provider != "compatible":
        return DEFAULTS[provider]
    raw = base_url.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL inválida. Informe uma URL HTTP(S), sem credenciais, query ou fragmento.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Base URL HTTP só é permitida para serviço local; use HTTPS em outros hosts.")
    return raw


def _read():
    if not AI_CONFIG_PATH.is_file():
        return {"providers": [], "default_id": None}
    raw = json.loads(AI_CONFIG_PATH.read_text(encoding="utf-8"))
    entries = raw.get("providers") if isinstance(raw, dict) else None
    if entries is None:
        # Migrate the original single-provider format in memory. Preserve its key.
        entries = [raw] if isinstance(raw, dict) and raw.get("api_key") else []
    normalized = []
    migrated = "providers" not in raw or any(not item.get("id") for item in entries) or "default_id" not in raw
    for item in entries:
        provider = item.get("provider")
        model = item.get("model", "")
        base = item.get("base_url") or DEFAULTS.get(provider, "")
        identifier = item.get("id") or uuid.uuid4().hex
        name = item.get("name") or provider.title()
        normalized.append({"id": identifier, "name": name, "provider": provider,
                           "model": model, "base_url": base, "api_key": item.get("api_key", "")})
    if isinstance(raw, dict) and raw.get("default_id"):
        default_id = raw["default_id"]
    elif normalized:
        old_index = raw.get("active", 0) if isinstance(raw, dict) else 0
        try:
            default_id = normalized[max(0, min(int(old_index), len(normalized)-1))]["id"]
        except (TypeError, ValueError):
            default_id = normalized[0]["id"]
    else:
        default_id = None
    if default_id not in {entry["id"] for entry in normalized}:
        default_id = normalized[0]["id"] if normalized else None
    result = {"providers": normalized, "default_id": default_id}
    if migrated:
        _write(result)
    return result


def _write(data):
    AI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".ai-provider-", dir=AI_CONFIG_PATH.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, AI_CONFIG_PATH)
        AI_CONFIG_PATH.chmod(0o600)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def public_entry(item):
    return {key: item[key] for key in ("id", "name", "provider", "model", "base_url") if key in item} | {"key_set": bool(item.get("api_key"))}


def status():
    data = _read()
    entries = data["providers"]
    active = next((item for item in entries if item["id"] == data["default_id"]), None)
    return {"configured": bool(entries), "provider": active["provider"] if active else None,
            "model": active["model"] if active else None, "base_url": active["base_url"] if active else "",
            "key_set": bool(active and active["api_key"]), "provider_count": len(entries),
            "providers": [public_entry(item) for item in entries], "default_id": data["default_id"],
            "active": next((i for i, item in enumerate(entries) if item["id"] == data["default_id"]), 0)}


def all_providers():
    return [public_entry(item) for item in _read()["providers"]]


def save(name, provider, model, api_key, base_url="", provider_id=None):
    name = name.strip()
    api_key = api_key.strip()
    if not name or len(name) > 80:
        raise ValueError("Informe um nome de provedor com até 80 caracteres.")
    if not api_key and not provider_id:
        raise ValueError("Informe a chave da API.")
    resolved_url = validate(provider, model, base_url)
    data = _read()
    current = next((item for item in data["providers"] if item["id"] == provider_id), None) if provider_id else None
    if provider_id and current is None:
        raise KeyError("Provedor não encontrado.")
    item = {"id": provider_id or uuid.uuid4().hex, "name": name, "provider": provider,
            "model": model.strip(), "base_url": resolved_url,
            "api_key": api_key or current["api_key"]}
    if current:
        data["providers"] = [item if old["id"] == provider_id else old for old in data["providers"]]
    else:
        data["providers"].append(item)
        data["default_id"] = item["id"]
    _write(data)
    return status()


def remove(provider_id):
    data = _read()
    kept = [item for item in data["providers"] if item["id"] != provider_id]
    if len(kept) == len(data["providers"]):
        raise KeyError("Provedor não encontrado.")
    data["providers"] = kept
    if data["default_id"] == provider_id:
        data["default_id"] = kept[0]["id"] if kept else None
    _write(data)
    return status()


def select(provider_id):
    data = _read()
    if not any(item["id"] == provider_id for item in data["providers"]):
        raise KeyError("Provedor não encontrado.")
    data["default_id"] = provider_id
    _write(data)
    return status()


def get_secret(provider_id=None):
    data = _read()
    identifier = provider_id or data["default_id"]
    item = next((entry for entry in data["providers"] if entry["id"] == identifier), None)
    if not item:
        raise KeyError("Provedor não encontrado.")
    return item


def _model_list(item):
    base, provider = item["base_url"].rstrip("/"), item["provider"]
    if provider == "gemini":
        url = f"{base}/models?key={urllib.parse.quote(item['api_key'], safe='')}"
        headers = {}
    else:
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {item['api_key']}"}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(2_000_001).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never expose response bodies: providers sometimes echo request metadata.
        if exc.code == 401 or exc.code == 403:
            raise RuntimeError("Autenticação rejeitada pelo provedor (401/403). Verifique a API Key e as permissões.") from None
        if exc.code == 404:
            raise RuntimeError("Endpoint não encontrado (404). Verifique a Base URL do provedor compatível.") from None
        raise RuntimeError(f"O provedor respondeu HTTP {exc.code} ao consultar modelos.") from None
    except (OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"Não foi possível consultar os modelos: {type(exc).__name__}.") from None
    rows = payload.get("models", []) if provider == "gemini" else payload.get("data", [])
    names = [str(row.get("name", "")).removeprefix("models/") if provider == "gemini" else str(row.get("id", ""))
             for row in rows if isinstance(row, dict)]
    if item["model"] not in names:
        raise RuntimeError(f"Autenticação aceita, mas o modelo '{item['model']}' não foi encontrado na lista do provedor.")
    return {"connected": True, "provider": item["provider"], "model": item["model"], "message": "Conexão confirmada; modelo listado pelo provedor."}


def list_models(provider_id):
    """Return provider model identifiers without exposing credentials or payloads."""
    item = get_secret(provider_id)
    models = _fetch_model_names(item)
    return {"provider_id": provider_id, "models": models, "current_model": item["model"]}


def list_draft_models(provider, api_key, base_url=""):
    if provider not in DEFAULTS:
        raise ValueError("Provedor não suportado.")
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("Informe a API Key para consultar os modelos.")
    base = DEFAULTS[provider] if provider != "compatible" else validate(provider, "model-placeholder", base_url)
    models = _fetch_model_names({"provider": provider, "api_key": api_key, "base_url": base})
    return {"provider": provider, "models": models}


def _fetch_model_names(item):
    """Query the official/compatible models endpoint and return bounded IDs only."""
    base, provider = item["base_url"].rstrip("/"), item["provider"]
    if provider == "gemini":
        url = f"{base}/models?key={urllib.parse.quote(item['api_key'], safe='')}"
        headers = {}
    else:
        url = f"{base}/models"
        headers = {"Authorization": f"Bearer {item['api_key']}"}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read(2_000_001).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Autenticação rejeitada pelo provedor (401/403).") from None
        raise RuntimeError(f"O provedor respondeu HTTP {exc.code} ao consultar modelos.") from None
    except (OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"Não foi possível consultar os modelos: {type(exc).__name__}.") from None
    rows = payload.get("models", []) if provider == "gemini" else payload.get("data", [])
    models = sorted({str(row.get("name", "")).removeprefix("models/") if provider == "gemini" else str(row.get("id", ""))
                     for row in rows if isinstance(row, dict)})
    return [name for name in models if name][:500]


def test_saved(provider_id):
    return _model_list(get_secret(provider_id))


def test_draft(provider, model, api_key, base_url=""):
    validate(provider, model, base_url)
    item = {"provider": provider, "model": model.strip(), "api_key": api_key.strip(),
            "base_url": validate(provider, model, base_url)}
    if not item["api_key"]:
        raise ValueError("Informe a chave da API para testar.")
    return _model_list(item)


def chat(messages, definitions):
    """One real provider chat completion; tool execution stays in the backend registry."""
    item = get_secret()
    provider = item["provider"]
    base = item["base_url"].rstrip("/")
    name_to_id = {definition["function"]["name"]: definition["id"] for definition in definitions}
    if provider == "gemini":
        contents = []
        for message in messages:
            role = message["role"]
            if role == "system":
                continue
            if role == "tool":
                call_id = message.get("meta", {}).get("tool_call_id")
                function_name = next((name for name, identifier in name_to_id.items() if identifier == call_id), "unknown")
                contents.append({"role": "user", "parts": [{"functionResponse": {"name": function_name, "response": {"result": message["content"]}}}]})
                continue
            meta = message.get("meta", {})
            if role == "assistant" and meta.get("tool_calls"):
                parts = [{"functionCall": {"name": next((name for name, identifier in name_to_id.items() if identifier == call["id"]), call["id"]), "args": call["arguments"]}} for call in meta["tool_calls"]]
                if message.get("content"):
                    parts.insert(0, {"text": message["content"]})
                contents.append({"role": "model", "parts": parts})
            else:
                contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": message["content"]}]})
        tools = [{"functionDeclarations": [{"name": x["function"]["name"], "description": x["function"]["description"], "parameters": x["function"]["parameters"]} for x in definitions]}] if definitions else []
        body = {"contents": contents, "tools": tools}
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"{base}/models/{item['model']}:generateContent?key={urllib.parse.quote(item['api_key'], safe='')}"
        headers = {"Content-Type": "application/json"}
    else:
        url = f"{base}/chat/completions"
        body = {"model": item["model"], "messages": [{"role": m["role"], "content": m["content"], **({"tool_calls": [{"id": call["id"], "type": "function", "function": {"name": next((name for name, identifier in name_to_id.items() if identifier == call["id"]), call["id"]), "arguments": json.dumps(call["arguments"], ensure_ascii=False)}} for call in m["meta"]["tool_calls"]]} if m.get("meta", {}).get("tool_calls") else {}), **({"tool_call_id": m["meta"]["tool_call_id"]} if m.get("role") == "tool" else {})} for m in messages], "temperature": 0.2}
        if definitions:
            body["tools"] = definitions
            body["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {item['api_key']}"}
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read(2_000_001).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise RuntimeError("Autenticação rejeitada pelo provedor (401/403).") from None
        if exc.code == 404:
            raise RuntimeError("Modelo ou endpoint não encontrado (404).") from None
        if exc.code == 400 and definitions:
            raise RuntimeError("O modelo/provedor recusou tool calling (HTTP 400). Troque para um modelo compatível em Configuração de IA; a conversa textual continua disponível.") from None
        raise RuntimeError(f"Provedor de IA retornou HTTP {exc.code}.") from None
    except (OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"Falha na chamada ao provedor: {type(exc).__name__}.") from None
    if provider == "gemini":
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "\n".join(part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str))
        calls = [{"id": name_to_id.get(part["functionCall"].get("name"), ""), "arguments": part["functionCall"].get("args", {})} for part in parts if isinstance(part, dict) and isinstance(part.get("functionCall"), dict)]
        if any(not call["id"] for call in calls):
            raise RuntimeError("O provedor solicitou uma ferramenta não registrada.")
    else:
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
        calls = []
        for call in message.get("tool_calls", []):
            function = call.get("function", {})
            identifier = name_to_id.get(function.get("name"), "")
            if not identifier:
                raise RuntimeError("O provedor solicitou uma ferramenta não registrada.")
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except ValueError:
                raise RuntimeError("O provedor retornou parâmetros de ferramenta inválidos.") from None
            calls.append({"id": identifier, "arguments": arguments})
    return {"text": text, "tool_calls": calls}
