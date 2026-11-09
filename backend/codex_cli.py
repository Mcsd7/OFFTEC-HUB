"""Termux-aware Codex CLI discovery and isolated, observable task execution."""
import hashlib
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from .config import DATA_DIR

MAX_WORKSPACE_BYTES = 250 * 1024 * 1024
MAX_CAPTURE_CHARS = 64_000
RUN_DIR = DATA_DIR / "codex_runs"
CODEX_WORKSPACES = DATA_DIR / "codex_workspaces"
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*)\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)


def _redact(text):
    value = str(text or "")
    for pattern in _SECRET_PATTERNS[:2]:
        value = pattern.sub(r"\1[REDACTED]", value)
    return _SECRET_PATTERNS[2].sub("[REDACTED]", value)


def _sanitize(value):
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    return value


def _which_codex():
    executable = shutil.which("codex")
    if not executable:
        return None
    return Path(executable)


def _candidates():
    """Find the public CLI and, when present, the Termux package's native pair."""
    public = _which_codex()
    if public is None:
        return {}
    try:
        resolved = public.resolve(strict=True)
    except OSError:
        resolved = public
    result = {"path_cli": {"id": "path_cli", "label": "Codex CLI (PATH)", "entry": str(public),
                           "kind": "path", "version": None}}

    # The Termux npm package links PATH's `codex` to codex.js (Node), but ships
    # an independent POSIX launcher and native ELF. The shell launcher must be
    # used for actual work because the Node shim reintroduces its private
    # libc++ path for child processes after Node itself starts.
    package_bin = resolved.parent if resolved.name in {"codex.js", "codex-exec.js"} else None
    if package_bin:
        native = package_bin / "codex.bin"
        launcher = package_bin / "codex"
        metadata = package_bin.parent / "package.json"
        version = None
        try:
            pkg = json.loads(metadata.read_text(encoding="utf-8"))
            version = pkg.get("version")
        except (OSError, ValueError):
            pass
        if launcher.is_file() and os.access(launcher, os.X_OK):
            result["main"] = {"id": "main", "label": "Codex CLI — launcher Termux", "entry": str(launcher),
                              "kind": "termux_launcher", "version": version, "bin_dir": str(package_bin)}
        if native.is_file() and os.access(native, os.X_OK):
            result["fallback"] = {"id": "fallback", "label": "Codex Fallback — binário nativo", "entry": str(native),
                                  "kind": "native", "version": version, "bin_dir": str(package_bin)}
    if "main" not in result:
        result["main"] = dict(result["path_cli"], id="main", label="Codex CLI (PATH)")
    return result


def _env_for(candidate):
    env = os.environ.copy()
    if candidate["kind"] == "node_shim":
        # The installed codex.js wrapper needs Node to start before it can set
        # its own native-binary environment. Termux currently exports this
        # package's private libc++ directory globally; that copy lacks a Node
        # symbol. Remove only the conflicting directory for the Node parent.
        bin_dir = candidate.get("bin_dir", "")
        inherited = [part for part in env.get("LD_LIBRARY_PATH", "").split(":") if part and part != bin_dir]
        if inherited:
            env["LD_LIBRARY_PATH"] = ":".join(inherited)
        else:
            env.pop("LD_LIBRARY_PATH", None)
        return env
    if candidate["kind"] != "native":
        return env
    bin_dir = candidate["bin_dir"]
    prefix = env.get("PREFIX", "/data/data/com.termux/files/usr").rstrip("/")
    blocked = {f"{prefix}/lib", f"{prefix}/libexec", "/data/data/com.termux/files/usr/lib",
               "/data/data/com.termux/files/usr/libexec"}
    inherited = [part for part in env.get("LD_LIBRARY_PATH", "").split(":") if part and part not in blocked]
    env["LD_LIBRARY_PATH"] = ":".join([bin_dir, *inherited])
    env["CODEX_SELF_EXE"] = candidate["entry"]
    env["CODEX_MANAGED_BY_NPM"] = "1"
    return env


def _invoke(candidate, args, timeout=12, cwd=None):
    try:
        return subprocess.run([candidate["entry"], *args], cwd=cwd, env=_env_for(candidate),
                              capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return exc


def _auth_status(candidate):
    result = _invoke(candidate, ["login", "status"], timeout=12)
    if isinstance(result, Exception):
        return {"authenticated": False, "detail": _redact(f"Verificação de autenticação falhou: {type(result).__name__}: {result}")}
    text = _redact((result.stdout + "\n" + result.stderr).strip())
    authenticated = result.returncode == 0 and bool(re.search(r"\blogged in\b", text, re.I)) and not bool(re.search(r"\bnot logged in\b|\bnot authenticated\b", text, re.I))
    if authenticated:
        detail = "Sessão Codex autenticada."
    elif result.returncode == 0:
        detail = "Codex respondeu, mas não confirmou uma sessão autenticada."
    else:
        detail = _redact(text[-800:] or f"codex login status encerrou com código {result.returncode}.")
    return {"authenticated": authenticated, "detail": detail}


def _inspect_candidate(candidate):
    version = _invoke(candidate, ["--version"])
    help_root = _invoke(candidate, ["--help"])
    help_exec = _invoke(candidate, ["exec", "--help"])
    errors = []
    for label, result in (("version", version), ("help", help_root), ("exec help", help_exec)):
        if isinstance(result, Exception):
            errors.append(f"{label}: {_redact(type(result).__name__ + ': ' + str(result))}")
        elif result.returncode:
            errors.append(f"{label}: {_redact((result.stderr or result.stdout).strip()[-800:])}")
    version_text = None
    if not isinstance(version, Exception) and version.returncode == 0:
        version_text = (version.stdout or version.stderr).strip()[:160]
    root_help_text = "" if isinstance(help_root, Exception) else help_root.stdout + help_root.stderr
    exec_help_text = "" if isinstance(help_exec, Exception) else help_exec.stdout + help_exec.stderr
    features = []
    if re.search(r"--json", exec_help_text):
        features.append("jsonl_progress")
    if re.search(r"--sandbox[\s\S]{0,300}workspace-write", exec_help_text):
        features.append("workspace_write_sandbox")
    if re.search(r"\bexec\b", root_help_text):
        features.append("exec")
    if "-C" in exec_help_text or "--cd" in exec_help_text:
        features.append("working_directory")
    if "--ephemeral" in exec_help_text:
        features.append("ephemeral_test")
    required = {"jsonl_progress", "workspace_write_sandbox", "exec"}
    if required - set(features):
        errors.append("Recursos necessários ausentes na ajuda instalada: " + ", ".join(sorted(required - set(features))))
    functional = not errors and required <= set(features)
    auth = _auth_status(candidate) if functional else {"authenticated": False, "detail": "Não verificado: CLI indisponível."}
    return {"id": candidate["id"], "label": candidate["label"], "entry": candidate["entry"],
            "kind": candidate["kind"], "installed": True, "functional": functional,
            "version": version_text or candidate.get("version"), "features": features,
            "authenticated": auth["authenticated"], "auth_detail": auth["detail"],
            "reason": "; ".join(errors) if errors else "Pronto."}


def inspect():
    candidates = _candidates()
    if not candidates:
        return {"installed": False, "functional": False, "auth_material_present": False,
                "authenticated": False, "version": None, "active_method": None, "methods": [],
                "reason": "Executável codex não encontrado no PATH."}
    # Do not report the broken Node shim as the working Termux integration.
    selected = {key: value for key, value in candidates.items() if key in {"main", "fallback"}}
    methods = [_inspect_candidate(candidate) for candidate in selected.values()]
    path_cli = candidates.get("path_cli")
    if path_cli and all(path_cli["entry"] != item["entry"] for item in selected.values()):
        path_probe = dict(path_cli, id="path_shim", label="Comando codex encontrado no PATH")
        methods.append(_inspect_candidate(path_probe))
    main = next((item for item in methods if item["id"] == "main"), None)
    fallback = next((item for item in methods if item["id"] == "fallback"), None)
    active = next((item for item in (main, fallback) if item and item["functional"] and item["authenticated"]), None)
    if active is None:
        active = next((item for item in (main, fallback) if item and item["functional"]), None)
    reasons = [f"{item['label']}: {item['reason']}" for item in methods if not item["functional"]]
    return {"installed": True, "functional": bool(active), "auth_material_present": any(x["authenticated"] for x in methods),
            "authenticated": any(x["authenticated"] for x in methods), "version": active["version"] if active else next((x["version"] for x in methods if x["version"]), None),
            "active_method": active["id"] if active else None, "methods": methods,
            "reason": "Pronto" if active and active["authenticated"] else "; ".join(reasons) or "Codex instalado; autenticação pendente."}


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


def _parse_event(line):
    try:
        value = json.loads(line)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _signal_process(process, sig):
    try:
        os.killpg(process.pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.terminate() if sig == signal.SIGTERM else process.kill()
        except OSError:
            pass


def run_task(project, prompt, confirmed=False, test_only=False, cancel_event=None, method="auto", on_update=None):
    if not confirmed:
        raise PermissionError("Confirme a execução no workspace isolado.")
    if method not in {"auto", "main", "fallback"}:
        raise ValueError("Método Codex inválido.")
    diagnostic = inspect()
    methods = {entry["id"]: entry for entry in diagnostic["methods"]}
    order = [method] if method != "auto" else [diagnostic.get("active_method") or "main", "fallback"]
    order = list(dict.fromkeys(order))
    selected = next((methods.get(item) for item in order if methods.get(item) and methods[item]["functional"] and methods[item]["authenticated"]), None)
    if selected is None:
        raise RuntimeError(diagnostic["reason"] or "Nenhum método Codex funcional e autenticado.")
    source = Path(project).expanduser().resolve()
    home = Path.home().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not source.is_dir() or source == Path("/") or not (home in source.parents or temp_root == source or temp_root in source.parents):
        raise ValueError("Projeto deve estar dentro do HOME do Termux ou da pasta temporária autorizada.")
    CODEX_WORKSPACES.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    workspace = CODEX_WORKSPACES / run_id
    _copy_project(source, workspace)
    if cancel_event is not None and cancel_event.is_set():
        return {"run_id": run_id, "workspace": str(workspace), "method": selected["id"], "returncode": 130,
                "status": "cancelled", "response": "", "events": [], "errors": [], "files": [],
                "stdout_tail": "", "stderr_tail": "Cancelado antes de iniciar."}

    executable = selected["entry"]
    command = [executable, "exec", "--json", "--sandbox", "read-only" if test_only else "workspace-write"]
    if test_only and "ephemeral_test" in selected["features"]:
        command.append("--ephemeral")
    command += ["-C", str(workspace), prompt]
    env = _env_for({"kind": selected["kind"], "entry": executable, "bin_dir": selected.get("entry").rsplit("/", 1)[0]})
    started_method = selected["id"]
    try:
        process = subprocess.Popen(command, cwd=workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, bufsize=1, start_new_session=True)
    except OSError as exc:
        # Retry only a launch failure, before the agent has had a chance to
        # execute any prompt or modify its workspace.
        fallback = methods.get("fallback")
        if method != "fallback" and started_method == "main" and fallback and fallback["functional"] and fallback["authenticated"]:
            selected = fallback
            started_method = "fallback"
            executable = selected["entry"]
            command[0] = executable
            env = _env_for({"kind": selected["kind"], "entry": executable, "bin_dir": selected["bin_dir"]})
            process = subprocess.Popen(command, cwd=workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, bufsize=1, start_new_session=True)
            launch_fallback_reason = _redact(f"Método principal não iniciou: {exc}; usando Codex Fallback.")
        else:
            raise RuntimeError(_redact(f"Falha ao iniciar Codex ({selected['label']}): {type(exc).__name__}: {exc}")) from None
    else:
        launch_fallback_reason = None

    lines = queue.Queue()
    def reader(stream, name):
        try:
            for line in iter(stream.readline, ""):
                lines.put((name, line))
        finally:
            lines.put((name, None))
    threads = [threading.Thread(target=reader, args=(process.stdout, "stdout"), daemon=True),
               threading.Thread(target=reader, args=(process.stderr, "stderr"), daemon=True)]
    for thread in threads:
        thread.start()
    stdout_parts, stderr_parts, events, assistant_messages, errors = [], [], [], [], []
    capture_size, done_streams, cancelled, timed_out = 0, set(), False, False
    deadline = time.monotonic() + 900
    next_status = 0.0
    while process.poll() is None or len(done_streams) < 2:
        if cancel_event is not None and cancel_event.is_set() and process.poll() is None:
            cancelled = True
            _signal_process(process, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _signal_process(process, signal.SIGKILL)
        if time.monotonic() >= deadline and process.poll() is None:
            timed_out = True
            _signal_process(process, signal.SIGKILL)
        try:
            name, line = lines.get(timeout=0.2)
        except queue.Empty:
            name, line = None, None
        if name and line is None:
            done_streams.add(name)
        elif name and line is not None:
            rendered = _redact(line)
            if name == "stdout":
                stdout_parts.append(rendered)
                event = _parse_event(line)
                if event:
                    event = _sanitize(event)
                    events.append(event)
                    if len(events) > 200:
                        del events[:len(events) - 200]
                    item = event.get("item", {}) if isinstance(event.get("item", {}), dict) else {}
                    if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                        assistant_messages.append(_redact(item["text"]))
                        if len(assistant_messages) > 100:
                            del assistant_messages[:-100]
                    if event.get("type") in {"error", "turn.failed"} or item.get("type") == "error":
                        errors.append(event)
                    if on_update:
                        on_update({"event": event, "events": events[-100:], "stdout_tail": "".join(stdout_parts)[-4000:],
                                   "stderr_tail": "".join(stderr_parts)[-4000:], "method": started_method})
            else:
                stderr_parts.append(rendered)
            capture_size += len(rendered)
            if capture_size > MAX_CAPTURE_CHARS:
                while capture_size > MAX_CAPTURE_CHARS and (stdout_parts or stderr_parts):
                    target = stdout_parts if stdout_parts else stderr_parts
                    capture_size -= len(target.pop(0))
        now = time.monotonic()
        if on_update and now >= next_status:
            on_update({"events": events[-100:], "stdout_tail": "".join(stdout_parts)[-4000:],
                       "stderr_tail": "".join(stderr_parts)[-4000:], "method": started_method})
            next_status = now + 1
        if timed_out and process.poll() is not None and len(done_streams) == 2:
            break
    for thread in threads:
        thread.join(timeout=1)
    returncode = process.wait()
    if timed_out:
        errors.append({"type": "timeout", "message": "A tarefa excedeu 900 segundos."})
    changed = subprocess.run(["git", "-c", "status.branch=false", "status", "--short", "--untracked-files=all"], cwd=workspace, capture_output=True, text=True, timeout=10, check=False).stdout.splitlines()
    result = {"run_id": run_id, "workspace": str(workspace), "method": started_method,
              "launch_fallback_reason": launch_fallback_reason, "returncode": returncode,
              "status": "cancelled" if cancelled else "error" if timed_out else "success" if returncode == 0 else "error",
              "response": "\n".join(assistant_messages)[-12000:], "events": events[-200:], "errors": errors,
              "files": changed, "stdout_tail": "".join(stdout_parts)[-4000:], "stderr_tail": "".join(stderr_parts)[-4000:]}
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_file = RUN_DIR / f"{run_id}.json"
    run_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    run_file.chmod(0o600)
    if on_update:
        on_update({"final": result})
    return result
