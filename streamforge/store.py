import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

class Store:
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path, timeout=15)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, title TEXT NOT NULL, created TEXT NOT NULL, payload TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.commit()

    def create(self, source: str, options: dict) -> int:
        payload = dict(source=source, options=options, status="Ожидает", clips=[], segments=[], error="")
        with self.connection:
            cursor = self.connection.execute("INSERT INTO jobs(title,created,payload) VALUES (?,?,?)", (Path(source).name or source, datetime.now(timezone.utc).isoformat(), json.dumps(payload, ensure_ascii=False)))
        return int(cursor.lastrowid)

    def load(self, job_id: int) -> dict:
        row = self.connection.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("Задача не найдена")
        return json.loads(row[0])

    def save(self, job_id: int, payload: dict) -> None:
        with self.connection:
            self.connection.execute("UPDATE jobs SET payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), job_id))

    def jobs(self) -> list[tuple[int, str, str]]:
        return self.connection.execute("SELECT id,title,created FROM jobs ORDER BY id DESC").fetchall()

    def settings(self) -> dict:
        row = self.connection.execute("SELECT value FROM settings WHERE key='options'").fetchone()
        return json.loads(row[0]) if row else {}

    def save_settings(self, settings: dict) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO settings VALUES ('options',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(settings, ensure_ascii=False),))

    def close(self) -> None:
        self.connection.close()
