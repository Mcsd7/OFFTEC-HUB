import json
import sqlite3
import os
from datetime import datetime, timezone
from ..config import DB_PATH


def connect():
    db = sqlite3.connect(DB_PATH)
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError:
        pass
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS operations (id INTEGER PRIMARY KEY, module TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, meta TEXT NOT NULL, created_at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS codex_conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, project_path TEXT, workspace_path TEXT, method TEXT NOT NULL DEFAULT 'auto', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS codex_messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES codex_conversations(id) ON DELETE CASCADE, role TEXT NOT NULL, content TEXT NOT NULL, meta TEXT NOT NULL, created_at TEXT NOT NULL)")


def record(module: str, action: str, status: str, result: dict):
    with connect() as db:
        cur = db.execute("INSERT INTO operations(module,action,status,created_at,result) VALUES(?,?,?,?,?)", (module, action, status, datetime.now(timezone.utc).isoformat(), json.dumps(result, ensure_ascii=False)))
        return cur.lastrowid


def recent(limit=20):
    with connect() as db:
        rows = db.execute("SELECT * FROM operations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(row), "result": json.loads(row["result"])} for row in rows]


def get(operation_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
    return {**dict(row), "result": json.loads(row["result"])} if row else None


def _now():
    return datetime.now(timezone.utc).isoformat()


def conversation_create(title="Nova conversa"):
    import uuid
    identifier, now = uuid.uuid4().hex, _now()
    with connect() as db:
        db.execute("INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)", (identifier, title[:100], now, now))
    return conversation_get(identifier)


def conversation_list():
    with connect() as db:
        rows = db.execute("SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS message_count FROM conversations c ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


def conversation_get(identifier):
    with connect() as db:
        row = db.execute("SELECT * FROM conversations WHERE id=?", (identifier,)).fetchone()
        if not row:
            return None
        messages = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,id", (identifier,)).fetchall()
    result = dict(row)
    result["messages"] = [{**dict(message), "meta": json.loads(message["meta"])} for message in messages]
    return result


def conversation_rename(identifier, title):
    with connect() as db:
        cur = db.execute("UPDATE conversations SET title=?,updated_at=? WHERE id=?", (title[:100], _now(), identifier))
    return conversation_get(identifier) if cur.rowcount else None


def conversation_delete(identifier):
    with connect() as db:
        db.execute("PRAGMA foreign_keys=ON")
        cur = db.execute("DELETE FROM conversations WHERE id=?", (identifier,))
        db.execute("DELETE FROM messages WHERE conversation_id=?", (identifier,))
    return cur.rowcount > 0


def message_add(conversation_id, role, content, meta=None):
    import uuid
    now = _now()
    with connect() as db:
        db.execute("INSERT INTO messages(id,conversation_id,role,content,meta,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, conversation_id, role, content, json.dumps(meta or {}, ensure_ascii=False), now))
        db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        if role == "user":
            row = db.execute("SELECT title FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if row and row["title"] == "Nova conversa":
                db.execute("UPDATE conversations SET title=? WHERE id=?", (content[:80], conversation_id))
    return conversation_get(conversation_id)["messages"][-1]


def codex_conversation_create(title="Nova conversa Codex", project_path=None, method="auto"):
    import uuid
    identifier, now = uuid.uuid4().hex, _now()
    with connect() as db:
        db.execute("INSERT INTO codex_conversations(id,title,project_path,method,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                   (identifier, title[:100], project_path, method, now, now))
    return codex_conversation_get(identifier)


def codex_conversation_list():
    with connect() as db:
        rows = db.execute("SELECT c.*, (SELECT COUNT(*) FROM codex_messages m WHERE m.conversation_id=c.id) AS message_count FROM codex_conversations c ORDER BY updated_at DESC").fetchall()
    return [dict(row) for row in rows]


def codex_conversation_get(identifier):
    with connect() as db:
        row = db.execute("SELECT * FROM codex_conversations WHERE id=?", (identifier,)).fetchone()
        if not row:
            return None
        messages = db.execute("SELECT * FROM codex_messages WHERE conversation_id=? ORDER BY created_at,id", (identifier,)).fetchall()
    result = dict(row)
    result["messages"] = [{**dict(message), "meta": json.loads(message["meta"])} for message in messages]
    return result


def codex_message_add(conversation_id, role, content, meta=None):
    import uuid
    now = _now()
    with connect() as db:
        db.execute("INSERT INTO codex_messages(id,conversation_id,role,content,meta,created_at) VALUES(?,?,?,?,?,?)",
                   (uuid.uuid4().hex, conversation_id, role, content, json.dumps(meta or {}, ensure_ascii=False), now))
        db.execute("UPDATE codex_conversations SET updated_at=? WHERE id=?", (now, conversation_id))
        if role == "user":
            row = db.execute("SELECT title FROM codex_conversations WHERE id=?", (conversation_id,)).fetchone()
            if row and row["title"] == "Nova conversa Codex":
                db.execute("UPDATE codex_conversations SET title=? WHERE id=?", (content[:80], conversation_id))
    return codex_conversation_get(conversation_id)["messages"][-1]


def codex_conversation_update_workspace(identifier, workspace_path, method):
    with connect() as db:
        db.execute("UPDATE codex_conversations SET workspace_path=?,method=?,updated_at=? WHERE id=?",
                   (workspace_path, method, _now(), identifier))


def codex_conversation_delete(identifier):
    with connect() as db:
        db.execute("PRAGMA foreign_keys=ON")
        cur = db.execute("DELETE FROM codex_conversations WHERE id=?", (identifier,))
        db.execute("DELETE FROM codex_messages WHERE conversation_id=?", (identifier,))
    return cur.rowcount > 0
