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


def test_saved(provider_id):
    return _model_list(get_secret(provider_id))


def test_draft(provider, model, api_key, base_url=""):
    validate(provider, model, base_url)
    item = {"provider": provider, "model": model.strip(), "api_key": api_key.strip(),
            "base_url": validate(provider, model, base_url)}
    if not item["api_key"]:
        raise ValueError("Informe a chave da API para testar.")
    return _model_list(item)
