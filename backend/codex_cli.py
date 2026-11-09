"""Constrained Codex CLI discovery and isolated project execution."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .config import DATA_DIR

MAX_WORKSPACE_BYTES = 250 * 1024 * 1024
RUN_DIR = DATA_DIR / "codex_runs"
CODEX_WORKSPACES = DATA_DIR / "codex_workspaces"


def inspect():
    executable = shutil.which("codex")
    if not executable:
        return {"installed": False, "functional": False, "auth_material_present": False, "version": None,
                "available_features": [], "reason": "Executável codex não encontrado no PATH."}
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=8, check=False)
        root_help = subprocess.run([executable, "--help"], capture_output=True, text=True, timeout=8, check=False)
        exec_help = subprocess.run([executable, "exec", "--help"], capture_output=True, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"installed": True, "functional": False, "auth_material_present": _auth_present(), "version": None,
                "available_features": [], "reason": f"Codex não inicia: {type(exc).__name__}."}
    if version.returncode or root_help.returncode or exec_help.returncode:
        detail = (version.stderr or root_help.stderr or exec_help.stderr or "comando help falhou").strip()[-1000:]
        return {"installed": True, "functional": False, "auth_material_present": _auth_present(), "version": None,
                "available_features": [], "reason": f"Ajuda/versão não funcionou: {detail}"}
    version_text = version.stdout.strip()[:120]
    features = []
    if "--json" in exec_help.stdout: features.append("jsonl_progress")
    if "--sandbox" in exec_help.stdout and "workspace-write" in exec_help.stdout: features.append("workspace_write_sandbox")
    if "exec" in root_help.stdout: features.append("exec")
    required = {"jsonl_progress", "workspace_write_sandbox", "exec"}
    missing = sorted(required - set(features))
    return {"installed": True, "functional": not missing, "auth_material_present": _auth_present(),
            "version": version_text, "available_features": features,
            "reason": "Pronto" if not missing else "Recursos necessários ausentes na ajuda instalada: " + ", ".join(missing)}


def _auth_present():
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    auth_file = codex_home / "auth.json"
    return bool(os.environ.get("CODEX_API_KEY") or auth_file.is_file())


def _files(root):
    result, total = [], 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or ".git" in path.relative_to(root).parts:
            continue
        size = path.stat().st_size
        total += size
        if total > MAX_WORKSPACE_BYTES:
            raise ValueError("Projeto excede o limite de cópia de 250 MiB.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result.append({"path": path.relative_to(root).as_posix(), "sha256": digest, "size_bytes": size})
    return result


def _copy_project(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if path.is_symlink() or ".git" in rel.parts or any(part in {"node_modules", ".venv", "venv", "build", ".gradle"} for part in rel.parts):
            continue
        name = path.name.lower()
        if name.startswith(".env") or name in {"auth.json", "credentials.json", "client_secret.json", "local.properties", "id_rsa"} or name.endswith((".pem", ".key", ".p12", ".pfx")):
            continue
        if not path.is_file():
            continue
        total += path.stat().st_size
        if total > MAX_WORKSPACE_BYTES:
            raise ValueError("Projeto excede o limite de cópia de 250 MiB.")
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    subprocess.run(["git", "init", "-q"], cwd=destination, capture_output=True, timeout=10, check=True)
    subprocess.run(["git", "add", "-A"], cwd=destination, capture_output=True, timeout=30, check=True)
    subprocess.run(["git", "-c", "user.name=OFFTEC HUB", "-c", "user.email=offtec@localhost", "commit", "-qm", "workspace baseline"], cwd=destination, capture_output=True, timeout=30, check=True)


def run_task(project, prompt, confirmed=False, test_only=False):
    if not confirmed:
        raise PermissionError("Confirme a execução no workspace isolado.")
    diagnostic = inspect()
    if not diagnostic["functional"]:
        raise RuntimeError(diagnostic["reason"])
    if not diagnostic["auth_material_present"]:
        raise RuntimeError("Codex não autenticado. Faça login no Termux e repita o diagnóstico.")
    source = Path(project).expanduser().resolve()
    home = Path.home().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not source.is_dir() or source == Path("/") or not (home in source.parents or temp_root == source or temp_root in source.parents):
        raise ValueError("Projeto deve estar dentro do HOME do Termux ou da pasta temporária autorizada.")
    CODEX_WORKSPACES.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    workspace = CODEX_WORKSPACES / run_id
    try:
        _copy_project(source, workspace)
        executable = shutil.which("codex")
        command = [executable, "exec", "--json"]
        if not test_only:
            command += ["--sandbox", "workspace-write"]
        command.append(prompt)
        completed = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=900, check=False)
        events, assistant_messages, errors = [], [], []
        for line in completed.stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            events.append(event)
            item = event.get("item", {})
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str): assistant_messages.append(item["text"])
            if event.get("type") in {"error", "turn.failed"}: errors.append(event)
        # Remove the committed baseline from comparison and read tracked worktree changes.
        changed = subprocess.run(["git", "status", "--short"], cwd=workspace, capture_output=True, text=True, timeout=10, check=False).stdout.splitlines()
        result = {"run_id": run_id, "workspace": str(workspace), "returncode": completed.returncode,
                  "status": "success" if completed.returncode == 0 else "error", "response": "\n".join(assistant_messages)[-12000:],
                  "events": events[-100:], "errors": errors, "files": changed,
                  "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]}
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        run_file = RUN_DIR / f"{run_id}.json"
        run_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        run_file.chmod(0o600)
        return result
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Execução do Codex excedeu 900 segundos.") from exc
    except Exception:
        if workspace.exists() and not any(workspace.iterdir()):
            workspace.rmdir()
        raise
