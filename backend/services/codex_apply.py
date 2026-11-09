"""Apply reviewed Codex workspace changes with backups and conflict checks."""
import os
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path, PurePosixPath

from .. import codex_cli

SECRET_NAMES = {"auth.json", "credentials.json", "client_secret.json", "local.properties", "id_rsa"}


def apply_workspace(project: Path, workspace: Path, status_lines):
    project = project.resolve(strict=True)
    workspace = workspace.resolve(strict=True)
    root = codex_cli.CODEX_WORKSPACES.resolve(strict=True)
    if root not in workspace.parents or not workspace.is_dir() or not (workspace / ".git").is_dir():
        raise ValueError("Workspace Codex inválido.")
    changed, conflicts, skipped = [], [], []
    total_bytes = 0
    operations = []
    for line in status_lines:
        if isinstance(line, str) and line.startswith("##"):
            continue
        if not isinstance(line, str) or len(line) < 4:
            continue
        state, raw = line[:2], line[3:]
        if "D" in state or "R" in state or "C" in state or raw.startswith('"'):
            skipped.append(raw)
            continue
        rel = PurePosixPath(raw)
        if rel.is_absolute() or not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
            conflicts.append(raw)
            continue
        name = rel.name.lower()
        if name.startswith(".env") or name in SECRET_NAMES or name.endswith((".pem", ".key", ".p12", ".pfx")):
            skipped.append(raw)
            continue
        source_file = workspace.joinpath(*rel.parts)
        if source_file.is_symlink() or not source_file.is_file():
            conflicts.append(raw)
            continue
        total_bytes += source_file.stat().st_size
        if total_bytes > 100 * 1024 * 1024:
            raise ValueError("As alterações excedem o limite de aplicação de 100 MiB.")
        target_file = project.joinpath(*rel.parts)
        parent = target_file.parent
        if any(node.is_symlink() for node in (parent, *parent.parents) if node != project.parent) or project not in target_file.resolve(strict=False).parents:
            conflicts.append(raw)
            continue
        if target_file.exists() and not target_file.is_file():
            conflicts.append(raw)
            continue
        baseline = subprocess.run(["git", "show", f"HEAD:{rel.as_posix()}"], cwd=workspace,
                                  capture_output=True, timeout=10, check=False)
        original_exists = target_file.exists()
        if baseline.returncode == 0:
            if not original_exists or target_file.is_symlink() or target_file.read_bytes() != baseline.stdout:
                conflicts.append(raw)
                continue
        elif original_exists:
            conflicts.append(raw)
            continue
        operations.append((raw, source_file, target_file))
    if conflicts:
        return {"applied": [], "conflicts": conflicts, "skipped": skipped,
                "message": "O projeto mudou desde a cópia Codex ou há caminhos inseguros. Nenhum arquivo foi aplicado."}
    stamp = uuid.uuid4().hex
    backup_root = root / "_apply_backups" / stamp
    backup_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    try:
        backup_root.parent.chmod(0o700)
    except OSError:
        pass
    backup_count, staged, replaced, backups, backup_modes = 0, [], [], {}, {}
    try:
        for raw, source_file, target_file in operations:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            if target_file.exists():
                backup_modes[raw] = stat.S_IMODE(target_file.stat().st_mode)
                backup_file = backup_root.joinpath(*PurePosixPath(raw).parts)
                backup_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_file, backup_file)
                backup_count += 1
                backups[raw] = backup_file
                try:
                    backup_file.chmod(0o600)
                except OSError:
                    pass
            fd, temp_name = tempfile.mkstemp(prefix=".offtec-codex-", dir=target_file.parent)
            try:
                with os.fdopen(fd, "wb") as output, source_file.open("rb") as source:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(temp_name, stat.S_IMODE(source_file.stat().st_mode) or 0o600)
                staged.append((raw, Path(temp_name), target_file))
            except Exception:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
                raise
        for raw, temp_path, target_file in staged:
            os.replace(temp_path, target_file)
            replaced.append((raw, target_file))
            changed.append(raw)
    except Exception:
        for raw, target_file in reversed(replaced):
            backup_file = backups.get(raw)
            if backup_file:
                fd, rollback_name = tempfile.mkstemp(prefix=".offtec-rollback-", dir=target_file.parent)
                with os.fdopen(fd, "wb") as output, backup_file.open("rb") as source:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(rollback_name, backup_modes.get(raw, 0o600))
                os.replace(rollback_name, target_file)
            else:
                target_file.unlink(missing_ok=True)
        raise
    finally:
        for _, temp_path, _ in staged:
            temp_path.unlink(missing_ok=True)
    return {"applied": changed, "conflicts": [], "skipped": skipped,
            "backup_count": backup_count,
            "message": "Alterações aplicadas após confirmação; os arquivos substituídos têm cópia privada de segurança."}
