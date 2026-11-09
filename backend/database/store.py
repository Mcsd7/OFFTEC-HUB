import json
import sqlite3
from datetime import datetime, timezone
from ..config import DB_PATH


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS operations (id INTEGER PRIMARY KEY, module TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, result TEXT NOT NULL)")


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
