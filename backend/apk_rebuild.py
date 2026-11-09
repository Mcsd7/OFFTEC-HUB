"""Isolated AI-assisted workspaces built from preserved ReaDroid outputs."""
import json
import shutil
import uuid
from pathlib import Path

from . import ai_coding
from .config import DATA_DIR, UPLOAD_DIR
from .database import store

PLAN_DIR = DATA_DIR / "rebuild_plans"
WORKSPACE_DIR = DATA_DIR / "workspaces"
MAX_COPY_BYTES = 250 * 1024 * 1024


def _source(operation):
    if operation["module"] != "apk_lab" or operation["status"] != "success" or operation["action"] not in {"inspect", "manifest", "jadx", "apktool"}:
        raise ValueError("Selecione uma análise ReaDroid concluída.")
    metadata = operation["result"]
    upload_id = metadata.get("upload_id")
    if not isinstance(upload_id, str) or len(upload_id) != 32 or any(c not in "0123456789abcdef" for c in upload_id):
        raise ValueError("A análise não tem referência válida ao APK enviado.")
    if operation["action"] == "manifest":
        root = UPLOAD_DIR / "reports" / upload_id
    else:
        root = UPLOAD_DIR / "output" / upload_id
    root = root.resolve()
    if UPLOAD_DIR.resolve() not in root.parents or not root.is_dir():
        raise ValueError("Os resultados isolados desta análise não estão disponíveis.")
    return root, metadata.get("result", {})


def _inventory(root, include_content=False):
    items, total = [], 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_COPY_BYTES:
            raise ValueError("Os resultados excedem 250 MiB; workspace não criado.")
        item = {"path": path.relative_to(root).as_posix(), "size_bytes": size}
        if include_content and len(items) < 30 and size <= 20000:
            try:
                item["content"] = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                pass
        items.append(item)
    return items


def create_plan(operation_id, request):
    if not ai_coding.get_config().get("configured"):
        raise ValueError("Configure um provedor de IA antes de solicitar o plano.")
    operation = store.get(operation_id)
    if not operation:
        raise ValueError("Operação de análise não encontrada.")
    source, analysis = _source(operation)
    files = _inventory(source, include_content=True)
    context = {"action": operation["action"], "result": analysis, "available_files": files,
               "source_recovered": False, "limitations": ["APK não contém necessariamente fontes originais", "ofuscação, código nativo, bibliotecas e dependências podem impedir reconstrução"]}
    encoded = json.dumps(context, ensure_ascii=False)
    if len(encoded) > 120000:
        encoded = encoded[:120000] + " [CONTEXTO TRUNCADO]"
    prompt = ("Crie um plano de modificações para trabalhar somente sobre os resultados de análise disponíveis. "
              "Não afirme que recuperou fontes originais. Identifique arquivos reais que podem ser alterados, riscos e limitações. "
              "Não proponha comandos arbitrários. Retorne JSON {summary:string,files:[]} e não faça alterações ainda.\n\n"
              f"Pedido do usuário: {request}\n\nDados ReaDroid e arquivos disponíveis:\n{encoded}")
    response = ai_coding._call(prompt)
    if response.get("files"):
        raise RuntimeError("A resposta de planejamento incluiu alterações; nenhum arquivo foi escrito.")
    plan_id = uuid.uuid4().hex
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    plan_file = PLAN_DIR / f"{plan_id}.json"
    payload = {"plan_id": plan_id, "operation_id": operation_id, "upload_id": source.name,
               "action": operation["action"], "source_root": str(source), "source_recovered": False,
               "analysis": analysis, "available_files": files, "request": request,
               "plan": str(response.get("summary", "")), "created_workspace": None}
    plan_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    plan_file.chmod(0o600)
    return {"plan_id": plan_id, "operation_id": operation_id, "action": operation["action"],
            "plan": payload["plan"], "available_files": files, "source_recovered": False,
            "limitations": context["limitations"], "confirmation_required": True}


def _load_plan(plan_id):
    if len(plan_id) != 32 or any(c not in "0123456789abcdef" for c in plan_id):
        raise ValueError("Plano inválido.")
    path = PLAN_DIR / f"{plan_id}.json"
    if not path.is_file():
        raise ValueError("Plano expirado ou não encontrado.")
    return json.loads(path.read_text(encoding="utf-8")), path


def _copy_workspace(source, destination, cancel_event=None):
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    for path in source.rglob("*"):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Cópia do workspace cancelada.")
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_COPY_BYTES:
            raise ValueError("Os resultados excedem 250 MiB; workspace incompleto removido.")
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def apply_plan(plan_id, request, confirmed, allow_build=False, cancel_event=None):
    if not confirmed:
        raise PermissionError("Confirmação explícita necessária antes de criar o workspace e modificar arquivos.")
    if not ai_coding.get_config().get("configured"):
        raise ValueError("Configure um provedor de IA antes de aplicar o plano.")
    plan, plan_file = _load_plan(plan_id)
    source = Path(plan["source_root"]).resolve()
    if UPLOAD_DIR.resolve() not in source.parents or not source.is_dir():
        raise ValueError("Os resultados de origem não estão disponíveis; o APK original não será alterado.")
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    workspace = WORKSPACE_DIR / f"apk-{plan_id[:12]}"
    try:
        _copy_workspace(source, workspace, cancel_event)
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
    (workspace / "OFFTEC_ANALYSIS.json").write_text(json.dumps({"operation_id": plan["operation_id"], "action": plan["action"], "analysis": plan["analysis"], "limitations": ["Fontes originais não foram recuperadas."]}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        changes = ai_coding.build_project(workspace, f"Implemente o pedido confirmado: {request}\n\nPlano aprovado:\n{plan['plan']}\n\nPreserve arquivos sem relação com o pedido. Este é um workspace isolado dos resultados ReaDroid.", cancel_event=cancel_event)
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise
    files = _inventory(workspace)
    build = {"attempted": False, "message": "Nenhum projeto Gradle detectado."}
    gradle_files = (workspace / "build.gradle").is_file() or (workspace / "build.gradle.kts").is_file() or (workspace / "settings.gradle").is_file() or (workspace / "settings.gradle.kts").is_file()
    if gradle_files and allow_build:
        executable = shutil.which("gradle")
        if executable:
            import subprocess
            try:
                completed = subprocess.run([executable, "-p", str(workspace), "assembleDebug", "--offline", "--no-daemon"], capture_output=True, text=True, timeout=300, check=False)
                build = {"attempted": True, "passed": completed.returncode == 0, "returncode": completed.returncode,
                         "stdout": completed.stdout[-6000:], "stderr": completed.stderr[-6000:]}
            except subprocess.TimeoutExpired:
                build = {"attempted": True, "passed": False, "message": "Build Gradle excedeu 300 segundos."}
        else:
            build = {"attempted": False, "message": "Projeto Gradle detectado, mas Gradle não está instalado."}
    elif gradle_files:
        build = {"attempted": False, "message": "Build pulado: exige autorização separada para executar scripts Gradle do workspace."}
    plan["created_workspace"] = str(workspace)
    plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    plan_file.chmod(0o600)
    return {"workspace": str(workspace), "source_recovered": False, "changes": changes,
            "files": files, "validation": {"file_count": len(files), "workspace_isolated": True}, "build": build}
