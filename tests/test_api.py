import io
import zipfile

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
