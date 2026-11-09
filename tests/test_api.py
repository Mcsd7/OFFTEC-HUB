import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
import pytest

from backend.main import TOKEN, app


def client():
    return TestClient(app)


def auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health_and_token_authentication():
    with client() as c:
        assert c.get("/api/v1/health").json()["status"] == "online"
        assert c.get("/api/v1/dashboard").status_code == 401
        assert c.get("/api/v1/dashboard", headers=auth()).status_code == 200


def test_bootstrap_requires_webview_origin():
    with client() as c:
        assert c.get("/api/v1/bootstrap").status_code == 403
        response = c.get("/api/v1/bootstrap", headers={"Origin": "https://appassets.androidplatform.net"})
        assert response.status_code == 200
        assert response.json()["token"] == TOKEN


def test_module_inventory_and_real_system_metrics():
    with client() as c:
        result = c.get("/api/v1/dashboard", headers=auth()).json()
        assert result["module_count"] >= 5
        assert result["system"]["cpu_cores"] == __import__("os").cpu_count()
        assert result["system"]["ram_total_bytes"] > 0
        assert all("state" in item and "actions" in item for item in result["modules"])


def test_apk_upload_and_realdroid_inspection():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest package='org.example.test'/>")
        apk.writestr("classes.dex", b"dex\n035\x00")
    with client() as c:
        upload = c.post("/api/v1/files/apk", headers=auth(), files={"file": ("tiny.apk", archive.getvalue(), "application/vnd.android.package-archive")})
        assert upload.status_code == 200, upload.text
        result = c.post("/api/v1/apk/operations", headers=auth(), json={"upload_id": upload.json()["upload_id"], "action": "inspect"})
        assert result.status_code == 200, result.text
        assert result.json()["result"]["dex_files"] == ["classes.dex"]
        assert result.json()["result"]["manifest"]["present"] is True


def test_invalid_apk_action_is_rejected():
    with client() as c:
        response = c.post("/api/v1/apk/operations", headers=auth(), json={"upload_id": "../etc/passwd", "action": "shell"})
        assert response.status_code == 422


def test_apk_results_virtual_directory_and_safe_file_preview(tmp_path, monkeypatch):
    from backend.config import UPLOAD_DIR
    root = UPLOAD_DIR / "output"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "sample-manifest.xml"
    path.write_text("<manifest package='example.test'/>", encoding="utf-8")
    with client() as c:
        listing = c.get("/api/v1/apk/results", headers=auth())
        assert listing.status_code == 200
        item = next(file for file in listing.json()["files"] if file["name"] == path.name)
        view = c.get(f"/api/v1/apk/results/{item['id']}", headers=auth())
        assert view.json()["content"] == path.read_text(encoding="utf-8")
        assert c.get("/api/v1/apk/results/../../etc/passwd", headers=auth()).status_code in {404, 422}
    path.unlink(missing_ok=True)


def test_dns_input_validation_and_lookup():
    with client() as c:
        invalid = c.post("/api/v1/security/dns", headers=auth(), json={"hostname": "example.com;id"})
        assert invalid.status_code == 422
        response = c.post("/api/v1/security/dns", headers=auth(), json={"hostname": "localhost"})
        assert response.status_code == 200
        assert response.json()["addresses"]


def test_portai_project_analysis_and_translation_preview(tmp_path):
    project = tmp_path / "sample"
    project.mkdir()
    (project / "strings.json").write_text('{"welcome":"Welcome to the app"}', encoding="utf-8")
    with client() as c:
        analysis = c.post("/api/v1/dev/analyze", headers=auth(), json={"path": str(project), "action": "analyze_project"})
        assert analysis.status_code == 200, analysis.text
        assert analysis.json()["result"]["tool"] == "OffTec PortAI"
        preview = c.post("/api/v1/dev/translation/preview", headers=auth(), json={"path": str(project), "source_language": "en", "targets": ["pt-BR"]})
        assert preview.status_code == 200, preview.text
        assert preview.json()["provider"] == "offline-review"
        assert preview.json()["entry_count"] == 1
        assert not preview.json()["entries"][0]["translations"]


def test_portai_translation_apply_writes_only_approved_copy(tmp_path):
    import json
    from backend.config import TRANSLATION_DIR
    project = tmp_path / "source"
    project.mkdir()
    source = project / "strings.json"
    source.write_text('{"welcome":"Welcome"}', encoding="utf-8")
    output = tmp_path / "localized"
    with client() as c:
        preview = c.post("/api/v1/dev/translation/preview", headers=auth(), json={"path": str(project), "source_language": "en", "targets": ["pt-BR"]}).json()
        session_file = TRANSLATION_DIR / f"{preview['session_id']}.json"
        saved = json.loads(session_file.read_text(encoding="utf-8"))
        entry = saved["entries"][0]
        entry["translations"] = {"pt-BR": "Boas-vindas"}
        entry["status"] = "review"
        session_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
        applied = c.post("/api/v1/dev/translation/apply", headers=auth(), json={"session_id": preview["session_id"], "selected_entries": [entry["entry_id"]], "targets": ["pt-BR"], "output_dir": str(output)})
        assert applied.status_code == 200, applied.text
        localized = output / "pt-BR" / "strings.json"
        assert json.loads(localized.read_text(encoding="utf-8"))["welcome"] == "Boas-vindas"
        assert json.loads(source.read_text(encoding="utf-8"))["welcome"] == "Welcome"


def test_package_install_rejects_unlisted_packages():
    with client() as c:
        response = c.post("/api/v1/terminal/install", headers=auth(), json={"packages": ["python;id"]})
        assert response.status_code == 400


def test_websocket_requires_session_token():
    with client() as c:
        with c.websocket_connect(f"/api/v1/events?token={TOKEN}") as ws:
            ws.send_text("ping")
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/api/v1/events?token=wrong"):
                pass


def test_ai_provider_config_keeps_secret_private_and_supports_multiple_providers(tmp_path, monkeypatch):
    from backend import ai_coding
    from backend import providers
    monkeypatch.setattr(ai_coding, "AI_CONFIG_PATH", tmp_path / "providers.json")
    monkeypatch.setattr(providers, "AI_CONFIG_PATH", tmp_path / "providers.json")
    with client() as c:
        first = c.put("/api/v1/ai/config", headers=auth(), json={"provider": "groq", "model": "model-a", "api_key": "secret-a"})
        assert first.status_code == 200
        assert "secret-a" not in first.text
        second = c.put("/api/v1/ai/config", headers=auth(), json={"provider": "gemini", "model": "model-b", "api_key": "secret-b"})
        assert second.status_code == 200
        assert second.json()["provider_count"] == 2
        assert second.json()["provider"] == "gemini"
        selected = c.put("/api/v1/ai/active/0", headers=auth())
        assert selected.json()["provider"] == "groq"
    assert (tmp_path / "providers.json").stat().st_mode & 0o077 == 0


def test_ai_provider_crud_preserves_key_and_selects_default(tmp_path, monkeypatch):
    from backend import providers
    monkeypatch.setattr(providers, "AI_CONFIG_PATH", tmp_path / "providers.json")
    with client() as c:
        created = c.post("/api/v1/ai/providers", headers=auth(), json={
            "name": "Gateway local", "provider": "compatible", "model": "chat-v2",
            "api_key": "private-test-key", "base_url": "http://localhost:8080/v1"})
        assert created.status_code == 200, created.text
        pid = created.json()["providers"][0]["id"]
        assert "private-test-key" not in created.text
        edited = c.put(f"/api/v1/ai/providers/{pid}", headers=auth(), json={
            "name": "Gateway renamed", "provider": "compatible", "model": "chat-v3",
            "api_key": "", "base_url": "http://localhost:8080/v1"})
        assert edited.status_code == 200, edited.text
        assert edited.json()["providers"][0]["name"] == "Gateway renamed"
        assert providers.get_secret(pid)["api_key"] == "private-test-key"
        assert c.put(f"/api/v1/ai/default/{pid}", headers=auth()).json()["default_id"] == pid
        assert c.delete(f"/api/v1/ai/providers/{pid}", headers=auth()).json()["configured"] is False
    assert (tmp_path / "providers.json").stat().st_mode & 0o077 == 0


def test_ai_provider_connection_checks_live_model_catalog_without_leaking_key(tmp_path, monkeypatch):
    import json
    from backend import providers
    monkeypatch.setattr(providers, "AI_CONFIG_PATH", tmp_path / "providers.json")

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, size=-1): return json.dumps({"data": [{"id": "model-real"}]}).encode()

    def fake_open(request, timeout):
        assert request.get_method() == "GET"
        assert request.full_url.endswith("/models")
        assert request.get_header("Authorization") == "Bearer connection-secret"
        return Reply()

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_open)
    with client() as c:
        response = c.post("/api/v1/ai/providers/test", headers=auth(), json={
            "provider": "openai", "model": "model-real", "api_key": "connection-secret"})
        assert response.status_code == 200
        assert response.json()["connected"] is True
        assert "connection-secret" not in response.text
        missing = c.post("/api/v1/ai/providers/test", headers=auth(), json={
            "provider": "openai", "model": "missing-model", "api_key": "connection-secret"})
        assert missing.json()["connected"] is False
        assert "não foi encontrado" in missing.json()["message"]


def test_ai_provider_rejects_unsafe_urls_and_sanitizes_auth_errors(tmp_path, monkeypatch):
    import urllib.error
    from backend import providers
    monkeypatch.setattr(providers, "AI_CONFIG_PATH", tmp_path / "providers.json")
    with client() as c:
        invalid = c.post("/api/v1/ai/providers", headers=auth(), json={
            "name": "Unsafe", "provider": "compatible", "model": "m1", "api_key": "secret",
            "base_url": "http://example.com/v1"})
        assert invalid.status_code == 400

    def unauthorized(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", {}, None)

    monkeypatch.setattr(providers.urllib.request, "urlopen", unauthorized)
    with client() as c:
        denied = c.post("/api/v1/ai/providers/test", headers=auth(), json={
            "provider": "openai", "model": "m1", "api_key": "must-not-leak"})
        assert denied.json()["connected"] is False
        assert "401/403" in denied.json()["message"]
        assert "must-not-leak" not in denied.text


def test_ai_tool_registry_executes_real_read_operations_and_rejects_unknown_parameters():
    with client() as c:
        catalog = c.get("/api/v1/ai/tools", headers=auth())
        assert catalog.status_code == 200
        tools = {item["id"]: item for item in catalog.json()["tools"]}
        assert tools["project.create"]["confirmation_required"] is True
        assert tools["system.snapshot"]["confirmation_required"] is False
        result = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "system.snapshot", "arguments": {}})
        assert result.status_code == 200 and result.json()["executed"] is True
        assert result.json()["result"]["cpu_cores"] > 0
        modules = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "modules.list", "arguments": {}})
        assert modules.status_code == 200 and modules.json()["result"]["modules"]
        extra = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "system.snapshot", "arguments": {"shell": "id"}})
        assert extra.status_code == 422
        unknown = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "shell.run", "arguments": {"cmd": "id"}})
        assert unknown.status_code == 404


def test_ai_tool_confirmation_and_project_analysis(tmp_path, monkeypatch):
    project = tmp_path / "real-project"
    project.mkdir()
    (project / "README.md").write_text("project evidence", encoding="utf-8")
    with client() as c:
        denied = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "project.create", "arguments": {"name": "NeedsConfirm"}})
        assert denied.status_code == 409
        analysis = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "project.analyze", "arguments": {"path": str(project)}})
        assert analysis.status_code == 200, analysis.text
        assert analysis.json()["executed"] is True
        assert analysis.json()["result"]["tool"] == "OffTec PortAI"


def test_registered_project_edit_requires_confirmation_and_writes_real_file(tmp_path, monkeypatch):
    from backend import ai_coding
    from backend.main import app
    monkeypatch.setattr(ai_coding, "get_config", lambda: {"configured": True})
    monkeypatch.setattr(ai_coding, "build_project", lambda project, request: _write_tool_file(project))
    project = tmp_path / "editable"
    project.mkdir()
    with client() as c:
        args = {"path": str(project), "request": "Crie uma tela de boas-vindas"}
        denied = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "project.edit", "arguments": args})
        assert denied.status_code == 409
        done = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "project.edit", "arguments": args, "confirmed": True})
        assert done.status_code == 200, done.text
        assert (project / "welcome.py").read_text() == "print('hello')"


def _write_tool_file(project):
    (project / "welcome.py").write_text("print('hello')", encoding="utf-8")
    return {"changed_files": ["welcome.py"], "file_count": 1}


def test_realdroid_rebuild_plan_and_apply_use_isolated_copy(tmp_path, monkeypatch):
    from backend import ai_coding
    from backend.config import UPLOAD_DIR
    from backend.main import app
    import backend.main as main_module

    class Analyzer:
        @staticmethod
        def inspect_apk(apk):
            return {"package": "org.example.demo", "dex_files": [], "manifest": {"present": True}}

    monkeypatch.setattr(main_module, "load_readroid", lambda: Analyzer)
    monkeypatch.setattr(ai_coding, "get_config", lambda: {"configured": True})
    monkeypatch.setattr(ai_coding, "_call", lambda prompt: {"summary": "Adicionar uma tela de informações, limitado aos arquivos disponíveis.", "files": []})
    monkeypatch.setattr(ai_coding, "build_project", lambda workspace, request, cancel_event=None: _write_rebuild_file(workspace))
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as apk:
        apk.writestr("AndroidManifest.xml", "<manifest package='org.example.demo'/>")
    with client() as c:
        uploaded = c.post("/api/v1/files/apk", headers=auth(), files={"file": ("original.apk", archive.getvalue(), "application/vnd.android.package-archive")})
        upload_id = uploaded.json()["upload_id"]
        original_hash = __import__("hashlib").sha256((UPLOAD_DIR / f"{upload_id}.apk").read_bytes()).hexdigest()
        analysis = c.post("/api/v1/apk/operations", headers=auth(), json={"upload_id": upload_id, "action": "inspect"})
        assert analysis.status_code == 200
        op_id = analysis.json()["operation_id"]
        plan = c.post("/api/v1/apk/rebuild/plan", headers=auth(), json={"operation_id": op_id, "request": "Adicionar uma tela de informações"})
        assert plan.status_code == 200, plan.text
        assert plan.json()["source_recovered"] is False
        denied = c.post("/api/v1/apk/rebuild/apply", headers=auth(), json={"plan_id": plan.json()["plan_id"], "request": "Aplicar", "confirmed": False})
        assert denied.status_code == 409
        started = c.post("/api/v1/apk/rebuild/apply", headers=auth(), json={"plan_id": plan.json()["plan_id"], "request": "Aplicar plano", "confirmed": True})
        assert started.status_code == 200, started.text
        state = c.get(f"/api/v1/apk/rebuild/tasks/{started.json()['task_id']}", headers=auth()).json()
        for _ in range(20):
            if state["status"] != "running": break
            import time; time.sleep(0.05)
            state = c.get(f"/api/v1/apk/rebuild/tasks/{started.json()['task_id']}", headers=auth()).json()
        assert state["status"] == "completed", state
        workspace = Path(state["result"]["workspace"])
        assert workspace.is_dir() and state["result"]["validation"]["workspace_isolated"] is True
        assert (workspace / "OFFTEC_ANALYSIS.json").is_file()
        assert (workspace / "modified.txt").read_text() == "AI change"
        assert __import__("hashlib").sha256((UPLOAD_DIR / f"{upload_id}.apk").read_bytes()).hexdigest() == original_hash
        assert (UPLOAD_DIR / "output" / upload_id).is_dir()


def _write_rebuild_file(workspace):
    (workspace / "modified.txt").write_text("AI change", encoding="utf-8")
    return {"summary": "Applied to isolated workspace", "changed_files": ["modified.txt"], "file_count": 1}


def test_offtec_ai_persistent_conversation_and_real_registered_tool_call(monkeypatch):
    from backend import ai_coding, providers
    monkeypatch.setattr(ai_coding, "get_config", lambda: {"configured": True})
    calls = {"count": 0}

    def provider_reply(messages, definitions):
        calls["count"] += 1
        if calls["count"] == 1:
            assert any(tool["id"] == "modules.list" for tool in definitions)
            return {"text": "Consultando inventário.", "tool_calls": [{"id": "modules.list", "arguments": {}}]}
        tool_message = next(message for message in reversed(messages) if message["role"] == "tool")
        import json
        result = json.loads(tool_message["content"])
        assert result["result"]["modules"]
        return {"text": f"Consultei {len(result['result']['modules'])} módulos reais.", "tool_calls": []}

    monkeypatch.setattr(providers, "chat", provider_reply)
    with client() as c:
        created = c.post("/api/v1/ai/conversations", headers=auth(), json={"title": "Teste OFFTEC AI"})
        conversation_id = created.json()["id"]
        response = c.post("/api/v1/ai/chat", headers=auth(), json={"conversation_id": conversation_id, "message": "Liste os módulos"})
        assert response.status_code == 200, response.text
        task_id = response.json()["task_id"]
        import time
        for _ in range(40):
            state = c.get(f"/api/v1/ai/chat/tasks/{task_id}", headers=auth()).json()
            if state["status"] != "running": break
            time.sleep(0.05)
        assert state["status"] == "completed", state
        messages = c.get(f"/api/v1/ai/conversations/{conversation_id}", headers=auth()).json()["messages"]
        assert any(item["role"] == "tool" and '"modules"' in item["content"] for item in messages)
        assert "módulos reais" in messages[-1]["content"]
        renamed = c.patch(f"/api/v1/ai/conversations/{conversation_id}", headers=auth(), json={"title": "Inventário local"})
        assert renamed.json()["title"] == "Inventário local"
        assert c.get(f"/api/v1/ai/conversations/{conversation_id}", headers=auth()).json()["messages"]
        assert c.request("DELETE", f"/api/v1/ai/conversations/{conversation_id}", headers=auth(), json={"confirmed": False}).status_code == 409
        assert c.request("DELETE", f"/api/v1/ai/conversations/{conversation_id}", headers=auth(), json={"confirmed": True}).json()["deleted"] is True


def test_offtec_ai_requires_confirmation_for_write_tool(tmp_path, monkeypatch):
    import pathlib
    from backend import ai_coding, providers
    monkeypatch.setattr(ai_coding, "get_config", lambda: {"configured": True})
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setattr(providers, "chat", lambda messages, definitions: {"text": "", "tool_calls": [{"id": "project.create", "arguments": {"name": "ConfirmedProject"}}]})
    with client() as c:
        response = c.post("/api/v1/ai/chat", headers=auth(), json={"message": "Crie um projeto"})
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        import time
        for _ in range(40):
            state = c.get(f"/api/v1/ai/chat/tasks/{task_id}", headers=auth()).json()
            if state["status"] != "running": break
            time.sleep(0.05)
        assert state["status"] == "completed", state
        conversation = c.get(f"/api/v1/ai/conversations/{response.json()['conversation_id']}", headers=auth()).json()
        pending = next(item for item in conversation["messages"] if item["meta"].get("pending_tools"))
        assert not (tmp_path / "Projects" / "ConfirmedProject").exists()
        denied = c.post(f"/api/v1/ai/conversations/{conversation['id']}/confirm-tool", headers=auth(), json={"message_id": pending["id"], "confirmed": False})
        assert denied.status_code == 409
        approved = c.post(f"/api/v1/ai/conversations/{conversation['id']}/confirm-tool", headers=auth(), json={"message_id": pending["id"], "confirmed": True})
        assert approved.status_code == 200
        assert (tmp_path / "Projects" / "ConfirmedProject").is_dir()


def test_offtec_ai_provider_adapter_maps_openai_tool_calls(monkeypatch):
    import json
    from backend import providers

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, size=-1):
            return json.dumps({"choices": [{"message": {"content": "", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "modules_list", "arguments": "{}"}}]}}]}).encode()

    def fake_open(request, timeout):
        payload = json.loads(request.data)
        assert payload["tools"][0]["function"]["name"] == "modules_list"
        assert request.get_header("Authorization") == "Bearer mock-key"
        return Reply()

    monkeypatch.setattr(providers, "get_secret", lambda: {"provider": "openai", "model": "mock-model", "api_key": "mock-key", "base_url": "https://example.test/v1"})
    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_open)
    result = providers.chat([{"role": "user", "content": "List modules", "meta": {}}], [{"id": "modules.list", "type": "function", "function": {"name": "modules_list", "description": "List", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}])
    assert result["tool_calls"] == [{"id": "modules.list", "arguments": {}}]


def test_offtec_ai_generation_can_be_cancelled_cooperatively(monkeypatch):
    import threading
    import time
    from backend import ai_coding, providers
    monkeypatch.setattr(ai_coding, "get_config", lambda: {"configured": True})
    started, release = threading.Event(), threading.Event()

    def slow_reply(messages, definitions):
        started.set()
        release.wait(4)
        return {"text": "late response", "tool_calls": []}

    monkeypatch.setattr(providers, "chat", slow_reply)
    with client() as c:
        started_response = c.post("/api/v1/ai/chat", headers=auth(), json={"message": "Long task"})
        task_id = started_response.json()["task_id"]
        assert started.wait(2)
        cancel = c.post(f"/api/v1/ai/chat/tasks/{task_id}/cancel", headers=auth())
        assert cancel.json()["status"] == "cancelling"
        release.set()
        for _ in range(40):
            state = c.get(f"/api/v1/ai/chat/tasks/{task_id}", headers=auth()).json()
            if state["status"] == "cancelled": break
            time.sleep(0.05)
        assert state["status"] == "cancelled"
        conversation = c.get(f"/api/v1/ai/conversations/{state['conversation_id']}", headers=auth()).json()
        assert "Geração cancelada" in conversation["messages"][-1]["content"]


def test_codex_cli_inspects_help_and_detects_required_features(monkeypatch):
    import os
    import subprocess
    from backend import codex_cli
    monkeypatch.setattr(codex_cli.shutil, "which", lambda name: "/usr/bin/codex")
    monkeypatch.setenv("CODEX_API_KEY", "dummy-only-presence")

    def fake_run(command, **kwargs):
        if command[-1] == "--version": return subprocess.CompletedProcess(command, 0, "codex 9.8.7\n", "")
        if command[-1] == "--help" and command[1] == "exec": return subprocess.CompletedProcess(command, 0, "Usage: codex exec [--json] [--sandbox workspace-write]", "")
        return subprocess.CompletedProcess(command, 0, "Commands: exec review", "")

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)
    status = codex_cli.inspect()
    assert status["functional"] is True
    assert status["version"] == "codex 9.8.7"
    assert status["auth_material_present"] is True


def test_codex_run_uses_isolated_copy_and_never_disables_approvals(tmp_path, monkeypatch):
    import json
    import subprocess
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    original = source / "app.py"
    original.write_text("original", encoding="utf-8")
    monkeypatch.setattr(codex_cli, "inspect", lambda: {"functional": True, "auth_material_present": True})
    monkeypatch.setattr(codex_cli.shutil, "which", lambda name: "/usr/bin/codex")

    def copy_project(src, dest):
        dest.mkdir(parents=True)
        (dest / "app.py").write_text("changed copy", encoding="utf-8")

    monkeypatch.setattr(codex_cli, "_copy_project", copy_project)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "/usr/bin/codex":
            assert "--yolo" not in command and "--full-auto" not in command
            assert command[command.index("--sandbox") + 1] == "workspace-write"
            event = {"type": "item.completed", "item": {"type": "agent_message", "text": "Codex response"}}
            return subprocess.CompletedProcess(command, 0, json.dumps(event) + "\n", "")
        return subprocess.CompletedProcess(command, 0, " M app.py\n", "")

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)
    result = codex_cli.run_task(source, "Fix app", confirmed=True)
    assert result["status"] == "success"
    assert result["response"] == "Codex response"
    assert result["files"] == [" M app.py"]
    assert original.read_text() == "original"
    assert commands[0][1:5] == ["exec", "--json", "--sandbox", "workspace-write"]


def test_codex_endpoints_require_confirmation_and_report_current_environment():
    with client() as c:
        status = c.get("/api/v1/codex/status", headers=auth())
        assert status.status_code == 200
        assert status.json()["installed"] is True
        refused = c.post("/api/v1/codex/run", headers=auth(), json={"path": "/tmp", "prompt": "inspect", "confirmed": False})
        assert refused.status_code == 409


def test_codex_workspace_copy_omits_common_secret_files(tmp_path):
    from backend.codex_cli import _copy_project
    source, destination = tmp_path / "project", tmp_path / "workspace"
    source.mkdir()
    (source / "main.py").write_text("print('ok')", encoding="utf-8")
    (source / ".env").write_text("API_KEY=private", encoding="utf-8")
    (source / "signing.pem").write_text("private key", encoding="utf-8")
    _copy_project(source, destination)
    assert (destination / "main.py").is_file()
    assert not (destination / ".env").exists()
    assert not (destination / "signing.pem").exists()


def test_ai_program_applies_only_relative_files_inside_selected_project(tmp_path, monkeypatch):
    from backend import ai_coding
    project = tmp_path / "workspace"
    project.mkdir()
    config = tmp_path / "providers.json"
    monkeypatch.setattr(ai_coding, "AI_CONFIG_PATH", config)
    ai_coding.save_config("groq", "test-model", "test-key")
    monkeypatch.setattr(ai_coding, "_call", lambda prompt: {"summary": "created file", "files": [{"path": "src/main.py", "content": "print('real file write')\n"}]})
    with client() as c:
        response = c.post("/api/v1/ai/program", headers=auth(), json={"path": str(project), "prompt": "Create the entry point"})
        assert response.status_code == 200, response.text
        assert response.json()["changed_files"] == ["src/main.py"]
        assert (project / "src/main.py").read_text() == "print('real file write')\n"
    monkeypatch.setattr(ai_coding, "_call", lambda prompt: {"summary": "escape", "files": [{"path": "../outside", "content": "bad"}]})
    with client() as c:
        response = c.post("/api/v1/ai/program", headers=auth(), json={"path": str(project), "prompt": "escape"})
        assert response.status_code == 422
    assert not (tmp_path / "outside").exists()
