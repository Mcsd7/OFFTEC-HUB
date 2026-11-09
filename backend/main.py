import asyncio
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import socket
import shutil
import subprocess
import uuid
from pathlib import Path
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import FRONTEND_DIR, LOG_DIR, MAX_UPLOAD_BYTES, TRANSLATION_DIR, UPLOAD_DIR
from .core.events import events
from .core.system import snapshot
from .database import store
from .models import AiProviderConfig, AiProviderUpsert, AiProviderTest, AiProviderModelsRequest, AiProgramRequest, ApkRebuildPlan, ApkRebuildApply, ConversationCreate, ConversationRename, ConversationDelete, ChatMessageRequest, ToolApproval, CodexRunRequest, CodexConversationCreate, CodexChatMessage, CodexApplyRequest, ProjectCreate, ProjectTestRequest, ToolExecution, ApkOperation, DnsRequest, PackageInstall, ProjectOperation, TranslationApply, TranslationPreview
from . import ai_coding
from . import providers as provider_store
from . import tool_registry
from .modules.manager import modules, load_netscope, load_readroid, load_portai
from .security import session_token
from .services.tasks import run_blocking
from .services import rebuild_tasks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("offtec.hub")
if not log.handlers:
    log.addHandler(RotatingFileHandler(LOG_DIR / "hub.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"))
try:
    (LOG_DIR / "hub.log").chmod(0o600)
except OSError:
    pass
TOKEN = session_token()
app = FastAPI(title="OFFTEC HUB API", version="0.1.0", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1", "https://appassets.androidplatform.net"], allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

@app.middleware("http")
async def allow_webview_private_network_preflight(request: Request, call_next):
    """Allow Chromium's PNA preflight only for the bundled app origin."""
    response = await call_next(request)
    origin = request.headers.get("origin", "")
    pna = request.headers.get("access-control-request-private-network", "").lower()
    if origin == "https://appassets.androidplatform.net" and pna == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

def authorize(authorization: str | None = Header(default=None)):
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not supplied or not __import__("hmac").compare_digest(supplied, TOKEN):
        raise HTTPException(status_code=401, detail="Sessão local inválida")

@app.on_event("startup")
async def startup():
    store.initialize()
    log.info("OFFTEC HUB API ready at 127.0.0.1:8765")

@app.get("/api/v1/health")
def health():
    return {"status": "online", "service": "offtec-hub", "version": app.version, "termux": Path("/data/data/com.termux/files/usr").exists()}

@app.get("/api/v1/bootstrap")
def bootstrap(request: Request):
    # Só a origem local do WebView recebe o token; o serviço nunca escuta na rede LAN.
    origin = request.headers.get("origin", "")
    if origin not in {"http://127.0.0.1:8765", "https://appassets.androidplatform.net"}:
        raise HTTPException(403, "Origem local do aplicativo necessária")
    return {"token": TOKEN}

@app.get("/api/v1/setup/status")
def setup_status():
    import importlib.util
    return {"termux": Path("/data/data/com.termux/files/usr").exists(),
            "python": shutil.which("python") is not None,
            "dependencies": {name: importlib.util.find_spec(name) is not None for name in ("fastapi", "uvicorn", "pydantic", "multipart")},
            "database": Path(__import__("backend.config", fromlist=["DB_PATH"]).DB_PATH).exists(),
            "modules_available": sum(1 for item in modules() if item["state"] == "ready")}

@app.get("/api/v1/dashboard", dependencies=[Depends(authorize)])
def dashboard():
    return {"system": snapshot(), "modules": modules(), "module_count": len(modules()), "history": store.recent(8)}

@app.get("/api/v1/modules", dependencies=[Depends(authorize)])
def list_modules():
    return {"modules": modules()}

@app.get("/api/v1/terminal/packages", dependencies=[Depends(authorize)])
def packages():
    executable = shutil.which("dpkg-query")
    if not executable:
        return {"available": False, "packages": [], "reason": "dpkg-query não encontrado"}
    try:
        result = __import__("subprocess").run([executable, "-W", "-f=${binary:Package}\t${Version}\n"], capture_output=True, text=True, timeout=12, check=False)
        rows = [line.split("\t", 1) for line in result.stdout.splitlines() if "\t" in line]
        return {"available": result.returncode == 0, "packages": [{"name": x[0], "version": x[1]} for x in rows[:1000]], "count": len(rows)}
    except Exception as exc:
        raise HTTPException(503, str(exc))

@app.post("/api/v1/terminal/install", dependencies=[Depends(authorize)])
async def install_packages(request: PackageInstall):
    allowed = {"python", "git", "openjdk-21", "jadx", "apktool", "aapt", "apksigner", "termux-api"}
    chosen = list(dict.fromkeys(request.packages))
    if not set(chosen) <= allowed:
        raise HTTPException(400, "A lista contém pacote fora da seleção autorizada do OFFTEC HUB.")
    pkg = shutil.which("pkg")
    if not pkg:
        raise HTTPException(503, "O gerenciador pkg do Termux não foi encontrado.")
    def run_install():
        import subprocess
        return subprocess.run([pkg, "install", "-y", *chosen], capture_output=True, text=True, timeout=900, check=False)
    try:
        completed = await run_blocking(run_install)
        result = {"packages": chosen, "returncode": completed.returncode,
                  "stdout": completed.stdout[-12000:], "stderr": completed.stderr[-12000:]}
        status = "success" if completed.returncode == 0 else "error"
        store.record("terminal", "install_packages", status, result)
        return result
    except Exception as exc:
        store.record("terminal", "install_packages", "error", {"packages": chosen, "error": str(exc)})
        raise HTTPException(503, str(exc))

@app.get("/api/v1/security/network", dependencies=[Depends(authorize)])
async def network_status():
    try:
        adapter = load_netscope()
        result = await run_blocking(adapter.read_connections)
        connections, denied = result
        counters = await run_blocking(adapter.net_bytes)
        address = await run_blocking(adapter.local_ip)
        op_result = {"available": True, "local_ip": address, "connection_count": len(connections),
                     "connections_sample": connections[:100], "access_restricted": denied,
                     "interface_bytes": {"received": counters[0], "transmitted": counters[1]} if counters else None,
                     "limitations": "O Android pode restringir /proc/net; resultado vazio não significa ausência de conexões."}
        store.record("netscope", "network_status", "success", op_result)
        return op_result
    except Exception as exc:
        store.record("netscope", "network_status", "error", {"error": str(exc)})
        raise HTTPException(503, str(exc))

@app.post("/api/v1/security/dns", dependencies=[Depends(authorize)])
async def dns_lookup(request: DnsRequest):
    hostname = request.hostname.rstrip(".")
    if not hostname or ".." in hostname:
        raise HTTPException(400, "Nome de host inválido")
    try:
        records = await run_blocking(socket.getaddrinfo, hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        addresses = sorted({item[4][0] for item in records})
        result = {"hostname": hostname, "addresses": addresses, "record_count": len(addresses)}
        store.record("security_lab", "dns_lookup", "success", result)
        return result
    except socket.gaierror as exc:
        store.record("security_lab", "dns_lookup", "error", {"hostname": hostname, "error": str(exc)})
        raise HTTPException(422, f"Falha na resolução DNS: {exc}")

@app.post("/api/v1/files/apk", dependencies=[Depends(authorize)])
async def upload_apk(file: UploadFile = File(...)):
    if not file.filename or Path(file.filename).suffix.lower() not in {".apk", ".apks", ".xapk", ".zip"}:
        raise HTTPException(400, "Selecione um APK ou arquivo compatível")
    upload_id = uuid.uuid4().hex
    target = UPLOAD_DIR / f"{upload_id}.apk"
    size = 0
    try:
        with target.open("wb") as output:
            while data := await file.read(1024 * 1024):
                size += len(data)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Arquivo excede 250 MiB")
                output.write(data)
        target.chmod(0o600)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"upload_id": upload_id, "file_name": Path(file.filename).name, "size_bytes": size}

@app.post("/api/v1/apk/operations", dependencies=[Depends(authorize)])
async def apk_operation(request: ApkOperation):
    apk = UPLOAD_DIR / f"{request.upload_id}.apk"
    if not apk.is_file():
        raise HTTPException(404, "APK enviado não encontrado")
    output_root = UPLOAD_DIR / "output" / request.upload_id
    report_root = UPLOAD_DIR / "reports" / request.upload_id
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    task_id = uuid.uuid4().hex[:12]
    await events.publish({"type": "progress", "task_id": task_id, "message": "Validando e analisando o arquivo"})
    try:
        analyzer = load_readroid()
        if request.action == "inspect":
            result = await run_blocking(analyzer.inspect_apk, apk)
        elif request.action == "manifest":
            result = await run_blocking(analyzer.analyze_manifest, apk, report_root)
        elif request.action == "jadx":
            result = await run_blocking(analyzer.decompile_with_jadx, apk, output_root)
        else:
            result = await run_blocking(analyzer.extract_smali_with_apktool, apk, output_root)
        op_id = store.record("apk_lab", request.action, "success", {"upload_id": request.upload_id, "result": result})
        await events.publish({"type": "progress", "task_id": task_id, "message": "Operação concluída", "operation_id": op_id})
        return {"operation_id": op_id, "task_id": task_id, "result": result}
    except Exception as exc:
        store.record("apk_lab", request.action, "error", {"error": str(exc)})
        await events.publish({"type": "error", "task_id": task_id, "message": str(exc)})
        raise HTTPException(422, str(exc))

@app.post("/api/v1/apk/rebuild/plan", dependencies=[Depends(authorize)])
async def apk_rebuild_plan(request: ApkRebuildPlan):
    if not ai_coding.get_config().get("configured"):
        raise HTTPException(409, "Configure um provedor de IA antes de solicitar um plano.")
    try:
        plan = await run_blocking(__import__("backend.apk_rebuild", fromlist=["create_plan"]).create_plan, request.operation_id, request.request)
        store.record("apk_rebuild", "plan", "success", {"plan_id": plan["plan_id"], "operation_id": request.operation_id})
        return plan
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        store.record("apk_rebuild", "plan", "error", {"operation_id": request.operation_id, "error": type(exc).__name__})
        raise HTTPException(422, f"Não foi possível montar o plano: {type(exc).__name__}.") from None

@app.post("/api/v1/apk/rebuild/apply", dependencies=[Depends(authorize)])
async def apk_rebuild_apply(request: ApkRebuildApply):
    if not request.confirmed:
        raise HTTPException(409, "Confirme explicitamente o plano antes de criar o workspace.")
    task_id = rebuild_tasks.start(request.plan_id, request.request, request.allow_build)
    await events.publish({"type": "progress", "task_id": task_id, "message": "Workspace isolado em preparação"})
    return {"task_id": task_id, "status": "running"}

@app.get("/api/v1/apk/rebuild/tasks/{task_id}", dependencies=[Depends(authorize)])
def apk_rebuild_task_status(task_id: str):
    result = rebuild_tasks.get(task_id)
    if result is None:
        raise HTTPException(404, "Tarefa não encontrada.")
    return result

@app.post("/api/v1/apk/rebuild/tasks/{task_id}/cancel", dependencies=[Depends(authorize)])
def apk_rebuild_task_cancel(task_id: str):
    result = rebuild_tasks.cancel(task_id)
    if result is None:
        raise HTTPException(404, "Tarefa não encontrada.")
    return result

@app.get("/api/v1/apk/results", dependencies=[Depends(authorize)])
def apk_results():
    roots = {"output": UPLOAD_DIR / "output", "reports": UPLOAD_DIR / "reports"}
    files = []
    for label, root in roots.items():
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            file_id = hashlib.sha256(f"{label}/{relative}".encode()).hexdigest()[:24]
            files.append({"id": file_id, "area": label, "name": path.name, "path": relative,
                          "size_bytes": path.stat().st_size, "modified": path.stat().st_mtime})
            if len(files) >= 500:
                return {"files": files, "truncated": True}
    return {"files": files, "truncated": False}

@app.get("/api/v1/apk/results/{file_id}", dependencies=[Depends(authorize)])
def apk_result_file(file_id: str):
    if len(file_id) != 24 or any(ch not in "0123456789abcdef" for ch in file_id):
        raise HTTPException(404, "Arquivo não encontrado")
    roots = (UPLOAD_DIR / "output", UPLOAD_DIR / "reports")
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if hashlib.sha256(f"{root.name}/{relative}".encode()).hexdigest()[:24] == file_id:
                if path.stat().st_size > 2_000_000:
                    raise HTTPException(413, "Prévia limitada a arquivos de até 2 MiB")
                try:
                    return {"name": path.name, "path": relative, "content": path.read_text(encoding="utf-8")}
                except UnicodeDecodeError:
                    return {"name": path.name, "path": relative, "binary": True, "size_bytes": path.stat().st_size}
    raise HTTPException(404, "Arquivo não encontrado")

@app.post("/api/v1/dev/analyze", dependencies=[Depends(authorize)])
async def analyze_project(request: ProjectOperation):
    path = _project_path(request.path)
    task_id = uuid.uuid4().hex[:12]
    await events.publish({"type": "progress", "task_id": task_id, "message": "Analisando estrutura e evidências"})
    try:
        portai = load_portai()
        result = await run_blocking(portai.analyze_project, path)
        op_id = store.record("dev_studio", request.action, "success", result)
        await events.publish({"type": "progress", "task_id": task_id, "message": "Análise concluída"})
        return {"operation_id": op_id, "result": result}
    except Exception as exc:
        store.record("dev_studio", request.action, "error", {"error": str(exc)})
        raise HTTPException(422, str(exc))

def _project_path(raw: str) -> Path:
    import tempfile
    path = Path(raw).expanduser().resolve()
    home = Path.home().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    # The OS temporary directory supports disposable projects and local testing.
    if not path.is_dir() or path == Path("/") or not (home in path.parents or temp_root == path or temp_root in path.parents):
        raise HTTPException(400, "Projeto inválido. Selecione uma pasta dentro do HOME do Termux.")
    return path

def _safe_output_path(raw: str, source: Path) -> Path:
    import tempfile
    requested = Path(raw).expanduser()
    output = requested.resolve()
    home = Path.home().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    allowed = home in output.parents or temp_root == output or temp_root in output.parents
    if not allowed or output == Path("/") or not requested.name:
        raise HTTPException(400, "A pasta de saída precisa ficar dentro do HOME do Termux ou da pasta temporária.")
    source = source.resolve()
    if output == source or output in source.parents or source in output.parents:
        raise HTTPException(400, "A saída precisa ficar separada do projeto original.")
    return output

@app.get("/api/v1/dev/projects", dependencies=[Depends(authorize)])
def dev_projects():
    home = Path.home().resolve()
    roots = [home / "Projects", home / "HUB"]
    ignored = {".git", ".gradle", "node_modules", ".venv", "venv", "build", "dist", "__pycache__"}
    markers = (("settings.gradle", "Android"), ("settings.gradle.kts", "Android"),
               ("build.gradle", "Android / Gradle"), ("pyproject.toml", "Python"),
               ("requirements.txt", "Python"), ("package.json", "Node.js"), ("Cargo.toml", "Rust"))
    found, seen = [], set()
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        candidates = [root]
        try:
            for child in root.iterdir():
                if child.is_dir() and not child.is_symlink() and not child.name.startswith("."):
                    candidates.append(child)
        except OSError:
            continue
        for item in candidates:
            try:
                resolved = item.resolve(strict=True)
                if resolved in seen or resolved == home or not (home == resolved or home in resolved.parents):
                    continue
                kind = next((label for marker, label in markers if (resolved / marker).is_file()), "Projeto")
                if (resolved / "android" / "settings.gradle").is_file() or (resolved / "backend").is_dir() and (resolved / "frontend").is_dir():
                    kind = "OFFTEC HUB" if resolved.name == "HUB" else "Android / backend"
                if resolved == root.resolve() and root.name == "Projects" and kind == "Projeto":
                    continue
                seen.add(resolved)
                found.append({"name": item.name, "path": str(resolved), "kind": kind})
                if len(found) >= 200:
                    return {"projects": found, "truncated": True}
            except OSError:
                continue
    return {"projects": found, "truncated": False}

@app.post("/api/v1/dev/projects", dependencies=[Depends(authorize)])
def create_project(request: ProjectCreate):
    root = Path.home() / "Projects"
    target = root / request.name
    if target.exists():
        raise HTTPException(409, "Já existe um projeto com esse nome.")
    root.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    return {"name": target.name, "path": str(target.resolve())}

@app.get("/api/v1/ai/config", dependencies=[Depends(authorize)])
def ai_config_status():
    return ai_coding.get_config()

@app.get("/api/v1/ai/providers", dependencies=[Depends(authorize)])
def ai_providers_list():
    return {"providers": provider_store.all_providers(), "default_id": provider_store.status().get("default_id")}

@app.post("/api/v1/ai/providers", dependencies=[Depends(authorize)])
def ai_provider_create(request: AiProviderUpsert):
    try:
        return provider_store.save(request.name, request.provider, request.model, request.api_key, request.base_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.put("/api/v1/ai/providers/{provider_id}", dependencies=[Depends(authorize)])
def ai_provider_update(provider_id: str, request: AiProviderUpsert):
    try:
        return provider_store.save(request.name, request.provider, request.model, request.api_key, request.base_url, provider_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.delete("/api/v1/ai/providers/{provider_id}", dependencies=[Depends(authorize)])
def ai_provider_delete(provider_id: str):
    try:
        return provider_store.remove(provider_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))

@app.put("/api/v1/ai/default/{provider_id}", dependencies=[Depends(authorize)])
def ai_provider_default(provider_id: str):
    try:
        return provider_store.select(provider_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))

@app.post("/api/v1/ai/providers/test", dependencies=[Depends(authorize)])
async def ai_provider_test(request: AiProviderTest):
    try:
        if request.provider_id:
            return await run_blocking(provider_store.test_saved, request.provider_id)
        if not request.provider or not request.model or not request.api_key:
            raise ValueError("Informe provedor, modelo e chave para testar.")
        return await run_blocking(provider_store.test_draft, request.provider, request.model, request.api_key, request.base_url)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        return {"connected": False, "message": str(exc)}

@app.get("/api/v1/ai/providers/{provider_id}/models", dependencies=[Depends(authorize)])
async def ai_provider_models(provider_id: str):
    try:
        return await run_blocking(provider_store.list_models, provider_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None

@app.post("/api/v1/ai/providers/models", dependencies=[Depends(authorize)])
async def ai_provider_draft_models(request: AiProviderModelsRequest):
    try:
        return await run_blocking(provider_store.list_draft_models, request.provider, request.api_key, request.base_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from None

@app.get("/api/v1/ai/tools", dependencies=[Depends(authorize)])
def ai_tools_catalog():
    return {"tools": tool_registry.describe_tools()}

@app.post("/api/v1/ai/tools/execute", dependencies=[Depends(authorize)])
async def ai_tool_execute(request: ToolExecution):
    try:
        outcome = await tool_registry.execute(request.tool_id, request.arguments, request.confirmed)
        store.record("ai_tools", request.tool_id, "success", outcome)
        return {"executed": True, **outcome}
    except HTTPException as exc:
        store.record("ai_tools", request.tool_id, "rejected", {"status": exc.status_code, "detail": exc.detail})
        raise
    except Exception as exc:
        store.record("ai_tools", request.tool_id, "error", {"error": type(exc).__name__})
        raise HTTPException(422, f"A operação falhou: {type(exc).__name__}.") from None

def _chat_tool_definitions():
    definitions = []
    for item in tool_registry.describe_tools():
        function_name = re.sub(r"[^A-Za-z0-9_]", "_", item["id"])
        definitions.append({"id": item["id"], "type": "function", "function": {
            "name": function_name, "description": item["description"], "parameters": item["parameters"]}})
    return definitions

async def _chat_continue(conversation_id: str, cancel_event=None):
    definitions = _chat_tool_definitions()
    for _ in range(4):
        conversation = store.conversation_get(conversation_id)
        messages = [{"role": "system", "content": "Você é o OFFTEC AI dentro do OFFTEC HUB. Responda em português quando adequado. Use ferramentas registradas para consultar dados reais. Nunca afirme que executou uma operação sem receber o resultado da ferramenta. Ações que alteram dados aguardam confirmação explícita do usuário."}]
        messages.extend({"role": row["role"], "content": row["content"], "meta": row["meta"]} for row in conversation["messages"][-40:])
        response = await run_blocking(provider_store.chat, messages, definitions)
        if cancel_event is not None and cancel_event.is_set():
            store.message_add(conversation_id, "assistant", "Geração cancelada. A chamada HTTP já enviada ao provedor pode ter terminado, mas ferramentas e respostas posteriores não foram processadas.")
            return store.conversation_get(conversation_id)
        calls = response["tool_calls"]
        if not calls:
            store.message_add(conversation_id, "assistant", response["text"] or "O provedor retornou uma resposta vazia.")
            return store.conversation_get(conversation_id)
        store.message_add(conversation_id, "assistant", response["text"], {"tool_calls": calls})
        pending = []
        for call in calls:
            if cancel_event is not None and cancel_event.is_set():
                store.message_add(conversation_id, "assistant", "Geração cancelada antes da próxima operação.")
                return store.conversation_get(conversation_id)
            spec = tool_registry.TOOLS.get(call["id"])
            if spec is None:
                store.message_add(conversation_id, "tool", json.dumps({"error": "Operação não registrada"}), {"tool_call_id": call["id"]})
                continue
            if spec["confirmation_required"]:
                pending.append({"tool_id": call["id"], "arguments": call["arguments"]})
                continue
            try:
                result = await tool_registry.execute(call["id"], call["arguments"], confirmed=False)
            except HTTPException as exc:
                result = {"error": exc.detail, "status": exc.status_code}
            store.message_add(conversation_id, "tool", json.dumps(result, ensure_ascii=False), {"tool_call_id": call["id"]})
        if pending:
            approval_message = store.message_add(conversation_id, "assistant", "A operação abaixo pode criar ou alterar dados. Revise os parâmetros e confirme para executá-la.", {"pending_tools": pending, "confirmation_required": True})
            conversation = store.conversation_get(conversation_id)
            conversation["pending_message_id"] = approval_message["id"]
            return conversation
    store.message_add(conversation_id, "assistant", "Interrompi após quatro ciclos de ferramentas para limitar a execução. Envie outra mensagem para continuar.")
    return store.conversation_get(conversation_id)

@app.get("/api/v1/ai/conversations", dependencies=[Depends(authorize)])
def ai_conversation_list():
    return {"conversations": store.conversation_list()}

@app.post("/api/v1/ai/conversations", dependencies=[Depends(authorize)])
def ai_conversation_create(request: ConversationCreate):
    return store.conversation_create(request.title)

@app.get("/api/v1/ai/conversations/{conversation_id}", dependencies=[Depends(authorize)])
def ai_conversation_get(conversation_id: str):
    conversation = store.conversation_get(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversa não encontrada.")
    return conversation

@app.patch("/api/v1/ai/conversations/{conversation_id}", dependencies=[Depends(authorize)])
def ai_conversation_rename(conversation_id: str, request: ConversationRename):
    conversation = store.conversation_rename(conversation_id, request.title)
    if not conversation:
        raise HTTPException(404, "Conversa não encontrada.")
    return conversation

@app.delete("/api/v1/ai/conversations/{conversation_id}", dependencies=[Depends(authorize)])
def ai_conversation_delete(conversation_id: str, request: ConversationDelete):
    if not request.confirmed:
        raise HTTPException(409, "Confirme a exclusão da conversa.")
    if not store.conversation_delete(conversation_id):
        raise HTTPException(404, "Conversa não encontrada.")
    return {"deleted": True}

@app.post("/api/v1/ai/chat", dependencies=[Depends(authorize)])
async def ai_chat(request: ChatMessageRequest):
    if not ai_coding.get_config().get("configured"):
        raise HTTPException(409, "Configure um provedor antes de iniciar uma conversa.")
    conversation = store.conversation_get(request.conversation_id) if request.conversation_id else None
    if request.conversation_id and not conversation:
        raise HTTPException(404, "Conversa não encontrada.")
    if not conversation:
        conversation = store.conversation_create()
    store.message_add(conversation["id"], "user", request.message)
    from .services import chat_tasks
    task_id = chat_tasks.start(conversation["id"], request.message)
    await events.publish({"type": "progress", "task_id": task_id, "message": "Consultando o provedor de IA"})
    return {"task_id": task_id, "conversation_id": conversation["id"], "status": "running"}

@app.get("/api/v1/ai/chat/tasks/{task_id}", dependencies=[Depends(authorize)])
def ai_chat_task_status(task_id: str):
    from .services import chat_tasks
    result = chat_tasks.get(task_id)
    if result is None:
        raise HTTPException(404, "Geração não encontrada.")
    return result

@app.post("/api/v1/ai/chat/tasks/{task_id}/cancel", dependencies=[Depends(authorize)])
def ai_chat_task_cancel(task_id: str):
    from .services import chat_tasks
    result = chat_tasks.cancel(task_id)
    if result is None:
        raise HTTPException(404, "Geração não encontrada.")
    return result

@app.post("/api/v1/ai/conversations/{conversation_id}/confirm-tool", dependencies=[Depends(authorize)])
async def ai_conversation_confirm_tool(conversation_id: str, request: ToolApproval):
    if not request.confirmed:
        raise HTTPException(409, "Confirmação explícita necessária.")
    conversation = store.conversation_get(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversa não encontrada.")
    pending_message = next((message for message in conversation["messages"] if message["id"] == request.message_id and message["role"] == "assistant"), None)
    if not pending_message or not pending_message["meta"].get("pending_tools"):
        raise HTTPException(404, "Ação pendente não encontrada.")
    results = []
    for item in pending_message["meta"]["pending_tools"]:
        try:
            result = await tool_registry.execute(item["tool_id"], item["arguments"], confirmed=True)
        except HTTPException as exc:
            result = {"error": exc.detail, "status": exc.status_code}
        store.message_add(conversation_id, "tool", json.dumps(result, ensure_ascii=False), {"tool_call_id": item["tool_id"]})
        results.append({"tool_id": item["tool_id"], **result})
    store.message_add(conversation_id, "assistant", "Operação confirmada e executada no backend. Resultado real:\n" + json.dumps(results, ensure_ascii=False))
    return store.conversation_get(conversation_id)

@app.get("/api/v1/codex/status", dependencies=[Depends(authorize)])
def codex_status():
    from . import codex_cli
    return codex_cli.inspect()

@app.get("/api/v1/codex/conversations", dependencies=[Depends(authorize)])
def codex_conversation_list():
    return {"conversations": store.codex_conversation_list()}

@app.post("/api/v1/codex/conversations", dependencies=[Depends(authorize)])
def codex_conversation_create(request: CodexConversationCreate):
    project = _project_path(request.path) if request.path else None
    conversation = store.codex_conversation_create(request.title, str(project) if project else None, request.method)
    project_path = conversation.pop("project_path", None)
    conversation["has_project"] = bool(project_path)
    conversation["project_name"] = Path(project_path).name if project_path else None
    conversation.pop("workspace_path", None)
    return conversation

@app.get("/api/v1/codex/conversations/{conversation_id}", dependencies=[Depends(authorize)])
def codex_conversation_get(conversation_id: str):
    conversation = store.codex_conversation_get(conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversa Codex não encontrada.")
    # Workspace internals are private implementation details, not UI data.
    conversation.pop("workspace_path", None)
    project_path = conversation.pop("project_path", None)
    conversation["has_project"] = bool(project_path)
    conversation["project_name"] = Path(project_path).name if project_path else None
    conversation.pop("workspace_path", None)
    for message in conversation["messages"]:
        message["meta"].pop("workspace", None)
    return conversation

@app.delete("/api/v1/codex/conversations/{conversation_id}", dependencies=[Depends(authorize)])
def codex_conversation_delete(conversation_id: str, request: ConversationDelete):
    if not request.confirmed:
        raise HTTPException(409, "Confirme a exclusão desta conversa.")
    if not store.codex_conversation_delete(conversation_id):
        raise HTTPException(404, "Conversa Codex não encontrada.")
    return {"deleted": True}

@app.post("/api/v1/codex/conversations/{conversation_id}/apply", dependencies=[Depends(authorize)])
def codex_conversation_apply(conversation_id: str, request: CodexApplyRequest):
    if not request.confirmed:
        raise HTTPException(409, "Confirme explicitamente a aplicação das alterações no projeto.")
    conversation = store.codex_conversation_get(conversation_id)
    if not conversation or not conversation.get("project_path"):
        raise HTTPException(409, "Esta conversa não tem um projeto autorizado associado.")
    latest = next((message for message in reversed(conversation["messages"])
                   if message["role"] == "assistant" and message["meta"].get("workspace")), None)
    if not latest or not latest["meta"].get("files"):
        raise HTTPException(409, "O Codex não retornou arquivos alterados para aplicar.")
    project = _project_path(conversation["project_path"])
    from .services.codex_apply import apply_workspace
    try:
        result = apply_workspace(project, Path(latest["meta"]["workspace"]), latest["meta"]["files"])
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(422, f"Não foi possível aplicar o workspace: {type(exc).__name__}.") from None
    status = "success" if result.get("applied") else "error" if result.get("conflicts") else "success"
    store.record("codex", "apply_workspace", status,
                 {"conversation_id": conversation_id, "applied": result.get("applied", []),
                  "conflicts": result.get("conflicts", []), "skipped": result.get("skipped", [])})
    store.codex_message_add(conversation_id, "tool", result.get("message", "Aplicação concluída."),
                            {"apply_result": True, "applied": result.get("applied", []),
                             "conflicts": result.get("conflicts", []), "skipped": result.get("skipped", [])})
    return result

@app.post("/api/v1/codex/chat", dependencies=[Depends(authorize)])
async def codex_chat(request: CodexChatMessage):
    conversation = store.codex_conversation_get(request.conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversa Codex não encontrada.")
    has_project = bool(conversation.get("project_path"))
    if has_project and not request.confirmed:
        raise HTTPException(409, "Confirme que o Codex pode editar a cópia isolada deste projeto.")
    method = request.method or conversation.get("method", "auto")
    if method != conversation.get("method"):
        store.codex_conversation_update_workspace(conversation["id"], conversation.get("workspace_path"), method)
    source = conversation.get("workspace_path") or conversation.get("project_path")
    if not source:
        from . import codex_cli
        source = codex_cli.CODEX_WORKSPACES / f"chat-{conversation['id']}"
        source.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not request.retry:
        store.codex_message_add(conversation["id"], "user", request.message)
    from .services import codex_chat_tasks
    task_id = codex_chat_tasks.start(conversation["id"], request.message, source,
                                     method, test_only=not has_project)
    return {"task_id": task_id, "conversation_id": conversation["id"], "status": "running"}

@app.post("/api/v1/codex/test", dependencies=[Depends(authorize)])
async def codex_test(request: CodexRunRequest):
    if not request.confirmed:
        raise HTTPException(409, "Confirme o teste de leitura no workspace temporário.")
    if request.path:
        project = _project_path(request.path)
    else:
        from . import codex_cli
        project = codex_cli.CODEX_WORKSPACES / f"read-only-{uuid.uuid4().hex}"
        project.mkdir(parents=True, mode=0o700)
    from .services import codex_tasks
    task_id = codex_tasks.start(project, "Responda somente CODEX_TEST_OK. Não altere arquivos nem execute comandos.", test_only=True, method=request.method)
    return {"task_id": task_id, "status": "running"}

@app.post("/api/v1/codex/run", dependencies=[Depends(authorize)])
async def codex_run(request: CodexRunRequest):
    if not request.confirmed:
        raise HTTPException(409, "Confirme a tarefa Codex antes de criar e modificar o workspace.")
    if request.path:
        project = _project_path(request.path)
    else:
        from . import codex_cli
        project = codex_cli.CODEX_WORKSPACES / f"task-{uuid.uuid4().hex}"
        project.mkdir(parents=True, mode=0o700)
    from .services import codex_tasks
    task_id = codex_tasks.start(project, request.prompt, test_only=False, method=request.method)
    return {"task_id": task_id, "status": "running"}

@app.get("/api/v1/codex/tasks/{task_id}", dependencies=[Depends(authorize)])
def codex_task_status(task_id: str):
    from .services import codex_tasks
    result = codex_tasks.get(task_id)
    if result is None:
        raise HTTPException(404, "Tarefa Codex não encontrada.")
    return result

@app.post("/api/v1/codex/tasks/{task_id}/cancel", dependencies=[Depends(authorize)])
def codex_task_cancel(task_id: str):
    from .services import codex_tasks
    result = codex_tasks.cancel(task_id)
    if result is None:
        raise HTTPException(404, "Tarefa Codex não encontrada.")
    return result

@app.put("/api/v1/ai/config", dependencies=[Depends(authorize)])
def ai_config_save(request: AiProviderConfig):
    try:
        return ai_coding.save_config(request.provider, request.model, request.api_key, request.base_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.put("/api/v1/ai/active/{index}", dependencies=[Depends(authorize)])
def ai_config_select(index: int):
    try:
        return ai_coding.select_config(index)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(400, str(exc))

@app.post("/api/v1/ai/program", dependencies=[Depends(authorize)])
async def ai_program(request: AiProgramRequest):
    if not request.confirmed:
        raise HTTPException(409, "Confirme explicitamente as alterações no projeto selecionado.")
    project = _project_path(request.path)
    if not ai_coding.get_config().get("configured"):
        raise HTTPException(409, "Configure uma API de IA antes de programar.")
    task_id = uuid.uuid4().hex[:12]
    await events.publish({"type": "progress", "task_id": task_id, "message": "Lendo arquivos e enviando contexto ao provedor"})
    try:
        result = await run_blocking(ai_coding.build_project, project, request.prompt)
        store.record("ai_coding", "program", "success", {"path": str(project), **result})
        await events.publish({"type": "progress", "task_id": task_id, "message": f"Concluído: {result['file_count']} arquivo(s) alterado(s)"})
        return {"task_id": task_id, "project": str(project), **result}
    except Exception as exc:
        store.record("ai_coding", "program", "error", {"path": str(project), "error": str(exc)})
        await events.publish({"type": "error", "task_id": task_id, "message": str(exc)})
        raise HTTPException(422, str(exc))

@app.post("/api/v1/ai/test", dependencies=[Depends(authorize)])
async def ai_test(request: ProjectTestRequest):
    import subprocess
    if not request.confirmed:
        raise HTTPException(409, "Confirme a execução dos testes do projeto selecionado.")
    project = _project_path(request.path)
    commands = []
    if (project / "pytest.ini").exists() or (project / "pyproject.toml").exists() or (project / "tests").is_dir():
        if shutil.which("pytest"):
            commands.append([shutil.which("pytest"), "-q"])
        elif shutil.which("python"):
            commands.append([shutil.which("python"), "-m", "pytest", "-q"])
    if (project / "gradlew").is_file():
        commands.append([str(project / "gradlew"), "test"])
    elif (project / "build.gradle").is_file() or (project / "build.gradle.kts").is_file():
        if shutil.which("gradle"):
            commands.append([shutil.which("gradle"), "test"])
    if (project / "package.json").is_file() and shutil.which("npm"):
        try:
            package = json.loads((project / "package.json").read_text(encoding="utf-8"))
            if package.get("scripts", {}).get("test"):
                commands.append([shutil.which("npm"), "test"])
        except (OSError, ValueError):
            pass
    if not commands:
        return {"tested": False, "message": "Nenhum executor de teste reconhecido foi encontrado no projeto."}
    outcomes = []
    for command in commands:
        try:
            result = await run_blocking(subprocess.run, command, cwd=project, capture_output=True, text=True, timeout=300, check=False)
            outcomes.append({"command": command[1:], "returncode": result.returncode, "stdout": result.stdout[-8000:], "stderr": result.stderr[-8000:]})
        except subprocess.TimeoutExpired:
            outcomes.append({"command": command[1:], "returncode": 124, "stdout": "", "stderr": "Tempo limite de 300 segundos excedido."})
    passed = all(item["returncode"] == 0 for item in outcomes)
    store.record("ai_coding", "test", "success" if passed else "error", {"path": str(project), "results": outcomes})
    return {"tested": True, "passed": passed, "results": outcomes}

def _translation_types():
    from .config import PORTAI_PATH
    import sys
    if not (PORTAI_PATH / "portai_translation" / "engine.py").is_file():
        raise RuntimeError("Motor de tradução do PortAI não encontrado no checkout configurado.")
    sys.path.insert(0, str(PORTAI_PATH))
    from portai_translation.engine import TranslationEngine
    from portai_translation.models import TranslationEntry, TranslationResult
    from portai_translation.providers import configured_provider
    return TranslationEngine, TranslationEntry, TranslationResult, configured_provider

@app.post("/api/v1/dev/translation/preview", dependencies=[Depends(authorize)])
async def translation_preview(request: TranslationPreview):
    root = _project_path(request.path)
    session_id = uuid.uuid4().hex
    try:
        Engine, Entry, Result, provider_factory = _translation_types()
        try:
            global_ai = provider_store.get_secret()
        except KeyError:
            global_ai = None
        if global_ai:
            class HubTranslationProvider:
                name = f"OFFTEC IA global · {global_ai['provider']}"

                def translate(self, entries, target, source):
                    output = {}
                    for offset in range(0, len(entries), 40):
                        rows = [{"id": item.entry_id, "text": item.source, "context": item.context}
                                for item in entries[offset:offset + 40]]
                        prompt = ("Traduza os textos do JSON mantendo intactos placeholders, variáveis, tags e IDs. "
                                  "Responda somente um objeto JSON que associe cada ID à tradução. "
                                  f"Idioma de origem: {source}; destino: {target}.\n" + json.dumps(rows, ensure_ascii=False))
                        response = provider_store.chat([
                            {"role": "system", "content": "Você traduz conteúdo de software. Preserve placeholders exatamente."},
                            {"role": "user", "content": prompt}], [])
                        text = response.get("text", "").strip()
                        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
                        decoded = json.loads(text)
                        if not isinstance(decoded, dict):
                            raise ValueError("A IA global retornou formato de tradução inválido.")
                        output.update({str(key): str(value) for key, value in decoded.items() if isinstance(value, str)})
                    return output

            translation_provider = HubTranslationProvider()
        else:
            translation_provider = provider_factory()
        engine = Engine(translation_provider, max_files=2000)
        result = await run_blocking(engine.scan, root, request.source_language)
        await run_blocking(engine.translate, result, request.targets)
        payload = result.to_dict()
        TRANSLATION_DIR.mkdir(parents=True, exist_ok=True)
        session_file = TRANSLATION_DIR / f"{session_id}.json"
        session_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        session_file.chmod(0o600)
        visible = payload["entries"][:300]
        response = {"session_id": session_id, "provider": result.provider, "project": str(root),
                    "targets": result.targets, "entry_count": len(payload["entries"]), "entries": visible,
                    "truncated": len(payload["entries"]) > len(visible),
                    "note": "Propostas ficam pendentes até você selecionar cada entrada e aplicar numa pasta externa."}
        store.record("dev_studio", "translation_preview", "success", {k: v for k, v in response.items() if k != "entries"})
        return response
    except Exception as exc:
        store.record("dev_studio", "translation_preview", "error", {"error": type(exc).__name__})
        raise HTTPException(422, f"Falha na prévia de tradução: {type(exc).__name__}.") from None

@app.post("/api/v1/dev/translation/apply", dependencies=[Depends(authorize)])
async def translation_apply(request: TranslationApply):
    session_file = TRANSLATION_DIR / f"{request.session_id}.json"
    if not session_file.is_file():
        raise HTTPException(404, "Sessão de tradução não encontrada")
    try:
        Engine, Entry, Result, _ = _translation_types()
        payload = json.loads(session_file.read_text(encoding="utf-8"))
        entries = [Entry(**item) for item in payload["entries"]]
        result = Result(**{**payload, "entries": entries})
        selected = set(request.selected_entries)
        valid_ids = {item.entry_id for item in entries}
        if not selected <= valid_ids:
            raise ValueError("A seleção contém entradas que não pertencem à sessão.")
        decisions = {(entry.entry_id, language): entry.entry_id in selected for entry in entries for language in request.targets}
        Engine.approve(result, decisions, request.targets)
        project = _project_path(str(result.project))
        output = (_safe_output_path(request.output_dir, project) if request.output_dir else
                  _safe_output_path(str(project.parent / f"{project.name}-localized-{request.session_id[:8]}"), project))
        if output.exists():
            raise ValueError("A pasta de saída automática já existe; gere uma nova prévia para escolher outro nome.")
        output.mkdir(parents=True, exist_ok=True)
        translator = Engine(None)
        report = await run_blocking(translator.apply, result, project, output, request.targets)
        output_result = {"output_dir": str(output), "report": str(report), "approved_entries": len(selected), "targets": request.targets}
        store.record("dev_studio", "translation_apply", "success", output_result)
        return output_result
    except Exception as exc:
        log.error("PortAI translation application failed (%s)", type(exc).__name__)
        store.record("dev_studio", "translation_apply", "error", {"error": type(exc).__name__})
        raise HTTPException(422, f"Falha ao aplicar tradução: {type(exc).__name__}.") from None

@app.get("/api/v1/history", dependencies=[Depends(authorize)])
def history():
    return {"operations": store.recent(100)}

@app.websocket("/api/v1/events")
async def websocket_events(ws: WebSocket):
    if ws.query_params.get("token", "") != TOKEN:
        await ws.close(code=4401)
        return
    await events.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        events.disconnect(ws)

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
