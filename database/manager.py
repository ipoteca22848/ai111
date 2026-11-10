import json
import sqlite3
from pathlib import Path
from database.models import Project

class Database:
    """One connection owned by the UI thread; all writes are transactional."""
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                source_path TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'imported',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                duration REAL NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS clips (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                start REAL NOT NULL CHECK(start>=0),
                end REAL NOT NULL CHECK(end>start),
                settings TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            );
            CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            PRAGMA user_version=1;
        """)

    def add_project(self, name: str, source: str, metadata: dict) -> int:
        if not name.strip():
            raise ValueError("Название проекта не должно быть пустым")
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO projects(name,source_path,duration,metadata) VALUES (?,?,?,?)",
                (name.strip(), str(Path(source).resolve()), float(metadata.get("duration", 0)), json.dumps(metadata, ensure_ascii=False)))
        return int(cursor.lastrowid)

    def projects(self) -> list[Project]:
        return [Project(**dict(row)) for row in self.connection.execute("SELECT * FROM projects ORDER BY id DESC")]

    def rename(self, project_id: int, name: str) -> None:
        if not name.strip():
            raise ValueError("Название проекта не должно быть пустым")
        with self.connection:
            self.connection.execute("UPDATE projects SET name=? WHERE id=?", (name.strip(), project_id))

    def delete(self, project_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM projects WHERE id=?", (project_id,))

    def statistics(self) -> dict:
        projects = self.connection.execute("SELECT count(*),coalesce(sum(duration),0) FROM projects").fetchone()
        clips = self.connection.execute("SELECT count(*),coalesce(sum(created_at>=strftime('%Y-%m-%dT%H:%M:%SZ','now','-7 days')),0) FROM clips").fetchone()
        return dict(projects=projects[0], duration=projects[1], clips=clips[0], week=clips[1])

    def activity(self) -> list[tuple[str, int]]:
        return [(r[0], r[1]) for r in self.connection.execute("""
            WITH RECURSIVE days(day) AS (
                SELECT date('now','-6 days') UNION ALL SELECT date(day,'+1 day') FROM days WHERE day<date('now')
            ) SELECT day,count(clips.id) FROM days LEFT JOIN clips ON date(clips.created_at)=day GROUP BY day ORDER BY day
        """)]

    def preference(self, key: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_preference(self, key: str, value: str) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO preferences VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def close(self) -> None:
        self.connection.close()
