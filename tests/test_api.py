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


def test_portai_project_analysis_and_translation_preview(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.providers._read", lambda: {"providers": [], "default_id": None})
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


def test_portai_translation_apply_writes_only_approved_copy(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.providers._read", lambda: {"providers": [], "default_id": None})
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
        dns = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "security.dns_lookup", "arguments": {"hostname": "localhost"}})
        assert dns.status_code == 200 and dns.json()["result"]["addresses"]
        extra = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "system.snapshot", "arguments": {"shell": "id"}})
        assert extra.status_code == 422
        unknown = c.post("/api/v1/ai/tools/execute", headers=auth(), json={"tool_id": "shell.run", "arguments": {"cmd": "id"}})
        assert unknown.status_code == 404


def test_project_analysis_and_translation_reject_outside_paths_and_output_overlap():
    from backend.main import _safe_output_path
    from fastapi import HTTPException
    project = Path.home() / "HUB"
    with client() as c:
        response = c.post("/api/v1/dev/analyze", headers=auth(), json={"path": "/etc", "action": "analyze_project"})
        assert response.status_code == 400
        translation = c.post("/api/v1/dev/translation/preview", headers=auth(), json={"path": "/etc/passwd", "targets": ["pt-BR"]})
        assert translation.status_code == 400
    with pytest.raises(HTTPException):
        _safe_output_path(str(project / "localized"), project)
    with pytest.raises(HTTPException):
        _safe_output_path("/etc/offtec-output", project)


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


def _codex_status(main, fallback=None, active="main"):
    methods = [dict(id="main", functional=True, authenticated=True, entry=str(main), kind="termux_launcher",
                    features=["jsonl_progress", "workspace_write_sandbox", "exec", "ephemeral_test"])]
    if fallback:
        methods.append(dict(id="fallback", functional=True, authenticated=True, entry=str(fallback), kind="native",
                            bin_dir=str(fallback.parent), features=["jsonl_progress", "workspace_write_sandbox", "exec", "ephemeral_test"]))
    return {"functional": True, "auth_material_present": True, "authenticated": True,
            "active_method": active, "methods": methods, "reason": "Pronto"}


def _fake_codex_executable(path, source):
    import sys
    path.write_text(f"#!{sys.executable}\n" + source, encoding="utf-8")
    path.chmod(0o700)
    return path


def test_codex_discovers_termux_launcher_and_direct_native_fallback(tmp_path, monkeypatch):
    import json
    from backend import codex_cli
    package = tmp_path / "@scope" / "codex-cli"
    bindir = package / "bin"
    bindir.mkdir(parents=True)
    shim = bindir / "codex.js"
    shim.write_text("// test shim", encoding="utf-8")
    (package / "package.json").write_text(json.dumps({"version": "0.163.0-termux.2"}), encoding="utf-8")
    cli = '''import sys
a=sys.argv[1:]
if a == ["--version"]: print("codex-cli 0.163.0")
elif a == ["--help"]: print("Commands:\\n  exec  Run Codex")
elif a == ["exec","--help"]: print("Usage: codex exec --json --sandbox workspace-write -C --ephemeral")
elif a == ["login","status"]: print("Logged in using ChatGPT")
'''
    _fake_codex_executable(bindir / "codex", cli)
    _fake_codex_executable(bindir / "codex.bin", cli)
    monkeypatch.setattr(codex_cli, "_which_codex", lambda: shim)
    candidates = codex_cli._candidates()
    assert candidates["main"]["entry"] == str(bindir / "codex")
    assert candidates["fallback"]["entry"] == str(bindir / "codex.bin")
    status = codex_cli.inspect()
    assert status["version"] == "codex-cli 0.163.0"
    assert status["authenticated"] is True
    assert status["active_method"] == "main"
    assert "ephemeral_test" in status["methods"][0]["features"]


def test_codex_authentication_check_does_not_accept_not_logged_in(tmp_path, monkeypatch):
    from backend import codex_cli
    executable = _fake_codex_executable(tmp_path / "codex", '''import sys
a=sys.argv[1:]
if a == ["--version"]: print("codex-cli 0.163.0")
elif a == ["--help"]: print("Commands: exec")
elif a == ["exec","--help"]: print("codex exec --json --sandbox workspace-write")
elif a == ["login","status"]: print("Not logged in")
''')
    monkeypatch.setattr(codex_cli, "_candidates", lambda: {"main": {"id": "main", "label": "test", "entry": str(executable), "kind": "path"}})
    status = codex_cli.inspect()
    assert status["functional"] is True
    assert status["authenticated"] is False
    assert status["methods"][0]["auth_detail"] == "Codex respondeu, mas não confirmou uma sessão autenticada."


def test_codex_cli_inspects_help_and_detects_required_features(monkeypatch):
    import subprocess
    from backend import codex_cli
    candidates = {
        "path_cli": {"id": "path_cli", "label": "PATH shim", "entry": "/usr/bin/codex.js", "kind": "path"},
        "main": {"id": "main", "label": "Termux launcher", "entry": "/pkg/bin/codex", "kind": "termux_launcher"},
        "fallback": {"id": "fallback", "label": "Native fallback", "entry": "/pkg/bin/codex.bin", "kind": "native", "bin_dir": "/pkg/bin"},
    }
    monkeypatch.setattr(codex_cli, "_candidates", lambda: candidates)

    def fake_run(command, **kwargs):
        if command[-1] == "--version": return subprocess.CompletedProcess(command, 0, "codex 9.8.7\n", "")
        if command[-1] == "--help" and "exec" in command: return subprocess.CompletedProcess(command, 0, "Usage: codex exec [--json] [--sandbox workspace-write] --ephemeral -C", "")
        if command[-2:] == ["login", "status"]: return subprocess.CompletedProcess(command, 0, "Logged in using ChatGPT", "")
        return subprocess.CompletedProcess(command, 0, "Commands: exec review", "")

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)
    status = codex_cli.inspect()
    assert status["functional"] is True
    assert status["version"] == "codex 9.8.7"
    assert status["auth_material_present"] is True
    assert status["active_method"] == "main"
    assert status["methods"][1]["authenticated"] is True


def test_codex_run_uses_isolated_copy_and_never_disables_approvals(tmp_path, monkeypatch):
    import io
    import json
    import subprocess
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    original = source / "app.py"
    original.write_text("original", encoding="utf-8")
    entry = str(tmp_path / "codex")
    monkeypatch.setattr(codex_cli, "inspect", lambda: _codex_status(Path(entry)))
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    monkeypatch.setattr(codex_cli, "RUN_DIR", tmp_path / "runs")

    def copy_project(src, dest):
        dest.mkdir(parents=True)
        (dest / "app.py").write_text("changed copy", encoding="utf-8")

    monkeypatch.setattr(codex_cli, "_copy_project", copy_project)
    commands = []

    class FakeProcess:
        returncode = 0
        pid = 1234
        def __init__(self):
            event = {"type": "item.completed", "item": {"type": "agent_message", "text": "Codex response"}}
            self.stdout = io.StringIO(json.dumps(event) + "\n")
            self.stderr = io.StringIO("")
        def poll(self): return self.returncode
        def wait(self, timeout=None): return self.returncode
        def terminate(self): self.returncode = -15
        def kill(self): self.returncode = -9

    def fake_popen(command, **kwargs):
        commands.append(command)
        assert "--yolo" not in command and "--full-auto" not in command
        assert command[command.index("--sandbox") + 1] == "workspace-write"
        return FakeProcess()

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, " M app.py\n", "")

    monkeypatch.setattr(codex_cli.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)
    result = codex_cli.run_task(source, "Fix app", confirmed=True, method="main")
    assert result["status"] == "success"
    assert result["response"] == "Codex response"
    assert result["files"] == [" M app.py"]
    assert original.read_text() == "original"
    assert commands[0][1:5] == ["exec", "--json", "--sandbox", "workspace-write"]
    assert commands[0][-3] == "-C"


def test_codex_auto_uses_fallback_and_returns_modified_file_manifest(tmp_path, monkeypatch):
    import json
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    original = source / "original.txt"
    original.write_text("preserve original", encoding="utf-8")
    argv_record = tmp_path / "fallback-argv.json"
    native = _fake_codex_executable(tmp_path / "codex.bin", f'''import json,sys
a=sys.argv[1:]
open({str(argv_record)!r},"w").write(json.dumps(a))
w=a[a.index("-C")+1]
open(w+"/new.txt","w").write("created in copy")
print(json.dumps({{"type":"item.completed","item":{{"type":"agent_message","text":"Fallback completed"}}}}),flush=True)
''')
    diagnostic = _codex_status(tmp_path / "main-not-functional", native, active="fallback")
    diagnostic["methods"][0]["functional"] = False
    diagnostic["methods"][0]["authenticated"] = False
    monkeypatch.setattr(codex_cli, "inspect", lambda: diagnostic)
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    monkeypatch.setattr(codex_cli, "RUN_DIR", tmp_path / "runs")
    result = codex_cli.run_task(source, "Create a file", confirmed=True, method="auto")
    argv = json.loads(argv_record.read_text(encoding="utf-8"))
    assert result["method"] == "fallback"
    assert result["response"] == "Fallback completed"
    assert any("new.txt" in item for item in result["files"])
    assert (Path(result["workspace"]) / "new.txt").read_text(encoding="utf-8") == "created in copy"
    assert original.read_text(encoding="utf-8") == "preserve original"
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert "--yolo" not in argv and "--full-auto" not in argv


def test_codex_retries_fallback_only_when_primary_cannot_spawn(tmp_path, monkeypatch):
    import json
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    broken = tmp_path / "broken-main"
    broken.write_text("#!/missing/codex-interpreter\n", encoding="utf-8")
    broken.chmod(0o700)
    started = tmp_path / "fallback-started"
    native = _fake_codex_executable(tmp_path / "codex.bin", f'''import json,sys
open({str(started)!r},"w").write("yes")
print(json.dumps({{"type":"turn.completed"}}),flush=True)
''')
    monkeypatch.setattr(codex_cli, "inspect", lambda: _codex_status(broken, native))
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    monkeypatch.setattr(codex_cli, "RUN_DIR", tmp_path / "runs")
    result = codex_cli.run_task(source, "No-op", confirmed=True)
    assert result["status"] == "success"
    assert result["method"] == "fallback"
    assert "não iniciou" in result["launch_fallback_reason"]
    assert started.is_file()


def test_codex_connection_probe_uses_read_only_sandbox_and_ephemeral_session(tmp_path, monkeypatch):
    import json
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("probe", encoding="utf-8")
    argv_file = tmp_path / "argv.json"
    executable = _fake_codex_executable(tmp_path / "codex", f'''import json,sys
a=sys.argv[1:]
open({str(argv_file)!r},"w").write(json.dumps(a))
print(json.dumps({{"type":"turn.completed"}}),flush=True)
''')
    monkeypatch.setattr(codex_cli, "inspect", lambda: _codex_status(executable))
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    monkeypatch.setattr(codex_cli, "RUN_DIR", tmp_path / "runs")
    result = codex_cli.run_task(source, "Read-only connectivity check", confirmed=True, test_only=True)
    argv = json.loads(argv_file.read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in argv
    assert "--yolo" not in argv and "--full-auto" not in argv


def test_codex_nonzero_exit_returns_detailed_but_redacted_error(tmp_path, monkeypatch):
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    executable = _fake_codex_executable(tmp_path / "codex", '''import sys
print('{"type":"turn.failed","error":{"message":"API_KEY=should-not-leak"}}',flush=True)
print("access_token=should-not-leak",file=sys.stderr,flush=True)
sys.exit(7)
''')
    monkeypatch.setattr(codex_cli, "inspect", lambda: _codex_status(executable))
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    monkeypatch.setattr(codex_cli, "RUN_DIR", tmp_path / "runs")
    result = codex_cli.run_task(source, "Fail", confirmed=True)
    assert result["status"] == "error" and result["returncode"] == 7
    assert "turn.failed" in result["stdout_tail"]
    assert "[REDACTED]" in result["stderr_tail"]
    assert "should-not-leak" not in result["stdout_tail"] + result["stderr_tail"]


def test_codex_cancellation_and_stderr_capture_redact_credentials(tmp_path, monkeypatch):
    import threading
    import time
    from backend import codex_cli
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("source", encoding="utf-8")
    started = tmp_path / "started"
    executable = _fake_codex_executable(tmp_path / "codex", f'''import sys,time
open({str(started)!r},"w").write("yes")
print("API_KEY=do-not-expose",file=sys.stderr,flush=True)
print('{{"type":"turn.started"}}',flush=True)
time.sleep(30)
''')
    monkeypatch.setattr(codex_cli, "inspect", lambda: _codex_status(executable))
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    monkeypatch.setattr(codex_cli, "RUN_DIR", tmp_path / "runs")
    cancel = threading.Event()
    result_box = {}
    worker = threading.Thread(target=lambda: result_box.setdefault("result", codex_cli.run_task(source, "Wait", True, cancel_event=cancel)))
    worker.start()
    for _ in range(40):
        if started.exists(): break
        time.sleep(0.05)
    cancel.set()
    worker.join(8)
    assert not worker.is_alive()
    result = result_box["result"]
    assert result["status"] == "cancelled"
    assert "[REDACTED]" in result["stderr_tail"]
    assert "do-not-expose" not in result["stderr_tail"]


def test_codex_endpoints_require_confirmation_and_report_current_environment():
    with client() as c:
        status = c.get("/api/v1/codex/status", headers=auth())
        assert status.status_code == 200
        assert status.json()["installed"] is True
        assert {item["id"] for item in status.json()["methods"]} >= {"main", "fallback"}
        assert status.json()["active_method"] in {"main", "fallback"}
        refused = c.post("/api/v1/codex/run", headers=auth(), json={"path": "/tmp", "prompt": "inspect", "confirmed": False})
        assert refused.status_code == 409
        invalid_method = c.post("/api/v1/codex/run", headers=auth(), json={"path": "/tmp", "prompt": "inspect", "confirmed": True, "method": "shell"})
        assert invalid_method.status_code == 422


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


def test_codex_chat_supports_an_empty_no_project_workspace(tmp_path, monkeypatch):
    import subprocess
    from backend import codex_cli
    source = tmp_path / "empty-source"
    source.mkdir()
    destination = tmp_path / "empty-workspace"
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path)
    codex_cli._copy_project(source, destination)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=destination,
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip()


def test_codex_task_cancel_endpoint_sets_cooperative_process_cancel(tmp_path, monkeypatch):
    import threading
    import time
    from backend import codex_cli
    started, release = threading.Event(), threading.Event()

    def fake_run(project, prompt, confirmed, test_only=False, cancel_event=None, method="auto", on_update=None):
        started.set()
        release.wait(4)
        assert cancel_event.is_set()
        return {"status": "cancelled", "run_id": "a" * 32, "workspace": str(tmp_path), "files": []}

    monkeypatch.setattr(codex_cli, "run_task", fake_run)
    source = tmp_path / "project"
    source.mkdir()
    with client() as c:
        created = c.post("/api/v1/codex/run", headers=auth(), json={"path": str(source), "prompt": "A task", "confirmed": True})
        task_id = created.json()["task_id"]
        assert started.wait(2)
        cancel = c.post(f"/api/v1/codex/tasks/{task_id}/cancel", headers=auth())
        assert cancel.json()["status"] == "cancelling"
        release.set()
        for _ in range(40):
            state = c.get(f"/api/v1/codex/tasks/{task_id}", headers=auth()).json()
            if state["status"] == "cancelled": break
            time.sleep(0.05)
        assert state["status"] == "cancelled"


def test_ai_program_applies_only_relative_files_inside_selected_project(tmp_path, monkeypatch):
    from backend import ai_coding
    project = tmp_path / "workspace"
    project.mkdir()
    config = tmp_path / "providers.json"
    monkeypatch.setattr(ai_coding, "AI_CONFIG_PATH", config)
    ai_coding.save_config("groq", "test-model", "test-key")
    monkeypatch.setattr(ai_coding, "_call", lambda prompt: {"summary": "created file", "files": [{"path": "src/main.py", "content": "print('real file write')\n"}]})
    with client() as c:
        refused = c.post("/api/v1/ai/program", headers=auth(), json={"path": str(project), "prompt": "Create the entry point"})
        assert refused.status_code == 409
        response = c.post("/api/v1/ai/program", headers=auth(), json={"path": str(project), "prompt": "Create the entry point", "confirmed": True})
        assert response.status_code == 200, response.text
        assert response.json()["changed_files"] == ["src/main.py"]
        assert (project / "src/main.py").read_text() == "print('real file write')\n"
    monkeypatch.setattr(ai_coding, "_call", lambda prompt: {"summary": "escape", "files": [{"path": "../outside", "content": "bad"}]})
    with client() as c:
        response = c.post("/api/v1/ai/program", headers=auth(), json={"path": str(project), "prompt": "escape", "confirmed": True})
        assert response.status_code == 422
    assert not (tmp_path / "outside").exists()


def test_project_test_execution_requires_confirmation(tmp_path, monkeypatch):
    import subprocess
    project = tmp_path / "run-tests"
    (project / "tests").mkdir(parents=True)
    monkeypatch.setattr("backend.main.shutil.which", lambda name: "/usr/bin/pytest" if name == "pytest" else None)
    monkeypatch.setattr("backend.main.run_blocking", lambda fn, *args, **kwargs: __import__("asyncio").to_thread(fn, *args, **kwargs))
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "ok", ""))
    with client() as c:
        data = {"path": str(project)}
        refused = c.post("/api/v1/ai/test", headers=auth(), json=data)
        assert refused.status_code == 409
        result = c.post("/api/v1/ai/test", headers=auth(), json={**data, "confirmed": True})
        assert result.status_code == 200 and result.json()["passed"] is True


def test_openrouter_is_a_global_provider_and_model_catalog_never_returns_key(tmp_path, monkeypatch):
    from backend import providers
    monkeypatch.setattr(providers, "AI_CONFIG_PATH", tmp_path / "providers.json")
    saved = providers.save("Router global", "openrouter", "openai/gpt-4.1-mini", "secret-test-key")
    assert saved["default_id"] == saved["providers"][0]["id"]
    request_seen = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit): return b'{"data":[{"id":"openai/gpt-4.1-mini"},{"id":"google/gemini-2.5-flash"}]}'

    def fake_urlopen(request, timeout):
        request_seen["url"] = request.full_url
        request_seen["authorization"] = request.get_header("Authorization")
        return Response()

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_urlopen)
    result = providers.list_models(saved["default_id"])
    assert result["models"] == ["google/gemini-2.5-flash", "openai/gpt-4.1-mini"]
    assert request_seen["url"] == "https://openrouter.ai/api/v1/models"
    assert request_seen["authorization"] == "Bearer secret-test-key"
    assert "secret-test-key" not in str(result)
    assert "secret-test-key" not in str(providers.status())
    draft = providers.list_draft_models("openrouter", "temporary-draft-key")
    assert draft["models"] == result["models"]
    assert "temporary-draft-key" not in str(draft)
    assert request_seen["authorization"] == "Bearer temporary-draft-key"


def test_codex_chat_without_project_is_persistent_and_read_only(tmp_path, monkeypatch):
    from backend.database import store
    from backend import main, codex_cli
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "hub.sqlite3")
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    store.initialize()
    called = {}
    monkeypatch.setattr("backend.services.codex_chat_tasks.start",
                        lambda conversation_id, prompt, source, method, test_only: called.update(
                            conversation_id=conversation_id, prompt=prompt, source=source,
                            method=method, test_only=test_only) or "task-real-cli")
    with client() as c:
        created = c.post("/api/v1/codex/conversations", headers=auth(), json={"title": "Pergunta sem projeto"})
        assert created.status_code == 200
        conversation_id = created.json()["id"]
        result = c.post("/api/v1/codex/chat", headers=auth(), json={
            "conversation_id": conversation_id, "message": "Explique API REST"})
        assert result.status_code == 200, result.text
        assert result.json()["task_id"] == "task-real-cli"
        assert called["test_only"] is True
        assert Path(called["source"]).is_dir()
        assert "Explique API REST" in called["prompt"]
        conversation = c.get(f"/api/v1/codex/conversations/{conversation_id}", headers=auth()).json()
        assert conversation["has_project"] is False
        assert conversation["messages"][0]["content"] == "Explique API REST"
        assert str(tmp_path) not in str(conversation)


def test_visual_project_catalog_detects_authorized_project_types(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    projects = tmp_path / "Projects"
    android = projects / "Mobile app"
    android.mkdir(parents=True)
    (android / "settings.gradle").write_text("rootProject.name='App'", encoding="utf-8")
    generic = projects / "Sample workspace"
    generic.mkdir()
    hub = tmp_path / "HUB"
    (hub / "backend").mkdir(parents=True)
    (hub / "frontend").mkdir()
    with client() as c:
        response = c.get("/api/v1/dev/projects", headers=auth())
        assert response.status_code == 200
        catalog = {item["name"]: item["kind"] for item in response.json()["projects"]}
        assert catalog["Mobile app"] == "Android"
        assert catalog["Sample workspace"] == "Projeto"
        assert catalog["HUB"] == "OFFTEC HUB"


def test_frontend_separates_global_ai_chat_and_codex_cli_experience():
    frontend = Path(__file__).parents[1] / "frontend/assets/js/app.js"
    source = frontend.read_text(encoding="utf-8")
    assert "['ai-config','Configuração de IA'" in source
    assert "['chat-ia','Chat IA'" in source
    assert "['codex','Codex CLI'" in source
    assert "function renderCodexPanel()" in source
    assert "function renderPage" in source and "if(id==='chat-ia')return `<section class=\"api-chat\"" in source
    assert "`${renderCodexPanel()}`" not in source
    assert 'id="codexPath"' not in source
    assert 'id="aiProjectPath"' not in source
    assert 'id="projectPath"' not in source


def test_codex_chat_requires_confirmation_for_visual_project_selection(tmp_path, monkeypatch):
    from backend.database import store
    from backend import codex_cli
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "hub.sqlite3")
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", tmp_path / "workspaces")
    store.initialize()
    project = tmp_path / "authorized-project"
    project.mkdir()
    called = []
    monkeypatch.setattr("backend.services.codex_chat_tasks.start",
                        lambda *args, **kwargs: called.append((args, kwargs)) or "task-project")
    with client() as c:
        refused_path = c.post("/api/v1/codex/conversations", headers=auth(), json={"path": "/etc"})
        assert refused_path.status_code == 400
        created = c.post("/api/v1/codex/conversations", headers=auth(), json={"path": str(project)})
        assert created.status_code == 200
        conversation_id = created.json()["id"]
        no_confirmation = c.post("/api/v1/codex/chat", headers=auth(), json={
            "conversation_id": conversation_id, "message": "Ajuste o código"})
        assert no_confirmation.status_code == 409
        assert called == []
        accepted = c.post("/api/v1/codex/chat", headers=auth(), json={
            "conversation_id": conversation_id, "message": "Ajuste o código", "confirmed": True})
        assert accepted.status_code == 200
        assert called and called[0][1]["test_only"] is False
        conversation = c.get(f"/api/v1/codex/conversations/{conversation_id}", headers=auth()).json()
        assert conversation["has_project"] is True
        assert str(project) not in str(conversation)


def test_translation_uses_global_ai_provider_when_configured(tmp_path, monkeypatch):
    from backend import main, providers
    from backend.database import store
    from backend.config import TRANSLATION_DIR
    project = tmp_path / "translation-source"
    project.mkdir()
    (project / "strings.json").write_text('{"welcome":"Welcome"}', encoding="utf-8")
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "history.sqlite3")
    monkeypatch.setattr(main, "TRANSLATION_DIR", tmp_path / "translation-sessions")
    monkeypatch.setattr(providers, "get_secret", lambda: {"provider": "openai", "model": "test", "api_key": "never-logged", "base_url": "https://example.invalid/v1"})
    seen = []
    def fake_chat(messages, definitions):
        import json
        prompt = messages[-1]["content"]
        seen.append(prompt)
        rows = json.loads(prompt.rsplit("\n", 1)[1])
        return {"text": json.dumps({row["id"]: "Boas-vindas" for row in rows}), "tool_calls": []}
    monkeypatch.setattr(providers, "chat", fake_chat)
    with client() as c:
        preview = c.post("/api/v1/dev/translation/preview", headers=auth(), json={"path": str(project), "source_language": "en", "targets": ["pt-BR"]})
        assert preview.status_code == 200, preview.text
        result = preview.json()
        assert result["provider"] == "OFFTEC IA global · openai"
        assert result["entries"][0]["translations"]["pt-BR"] == "Boas-vindas"
        assert "Welcome" in seen[0]
        assert "never-logged" not in str(result)
        assert "never-logged" not in str(seen)


def test_codex_workspace_apply_requires_confirmation_backs_up_and_rejects_conflicts(tmp_path, monkeypatch):
    import subprocess
    from backend import codex_cli
    from backend.database import store
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "hub.sqlite3")
    workspaces = tmp_path / "codex-workspaces"
    monkeypatch.setattr(codex_cli, "CODEX_WORKSPACES", workspaces)
    store.initialize()
    project = tmp_path / "authorized"
    project.mkdir()
    original = project / "main.py"
    original.write_text("before = True\n", encoding="utf-8")
    workspace = workspaces / "run-one"
    codex_cli._copy_project(project, workspace)
    (workspace / "main.py").write_text("after = True\n", encoding="utf-8")
    (workspace / "new.py").write_text("created = True\n", encoding="utf-8")
    changed = subprocess.run(["git", "status", "--short", "--untracked-files=all"], cwd=workspace,
                             capture_output=True, text=True, check=True).stdout.splitlines()
    conversation = store.codex_conversation_create("Apply changes", str(project), "auto")
    store.codex_conversation_update_workspace(conversation["id"], str(workspace), "main")
    store.codex_message_add(conversation["id"], "assistant", "Implemented files.",
                            {"workspace": str(workspace), "files": changed})
    with client() as c:
        refused = c.post(f"/api/v1/codex/conversations/{conversation['id']}/apply", headers=auth(), json={"confirmed": False})
        assert refused.status_code == 409
        result = c.post(f"/api/v1/codex/conversations/{conversation['id']}/apply", headers=auth(), json={"confirmed": True})
        assert result.status_code == 200, result.text
        assert set(result.json()["applied"]) == {"main.py", "new.py"}, result.json()
        assert result.json()["backup_count"] == 1
    assert original.read_text(encoding="utf-8") == "after = True\n"
    assert (project / "new.py").read_text(encoding="utf-8") == "created = True\n"
    backup = next((workspaces / "_apply_backups").rglob("main.py"))
    assert backup.read_text(encoding="utf-8") == "before = True\n"

    # A concurrent user edit since the workspace snapshot must prevent all writes.
    (original).write_text("concurrent user edit\n", encoding="utf-8")
    conflicted = c.post(f"/api/v1/codex/conversations/{conversation['id']}/apply", headers=auth(), json={"confirmed": True})
    assert conflicted.status_code == 200
    assert conflicted.json()["applied"] == []
    assert set(conflicted.json()["conflicts"]) == {"main.py", "new.py"}
    assert original.read_text(encoding="utf-8") == "concurrent user edit\n"
