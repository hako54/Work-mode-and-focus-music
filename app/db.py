"""SQLite kalıcı depolama (Railway volume üzerinde /data/app.db)."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .profiles import default_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    style_key TEXT NOT NULL,
    prompt TEXT NOT NULL,
    name TEXT,
    audio_path TEXT,
    duration_sec REAL,
    image_path TEXT,
    exclusive INTEGER NOT NULL DEFAULT 0   -- yalnızca derleme için üretildi
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,                    -- daily | short | compilation | mix
    track_id INTEGER REFERENCES tracks(id),
    parent_id INTEGER REFERENCES videos(id),  -- short -> daily
    style_key TEXT,
    title TEXT,
    description TEXT,
    tags TEXT,
    thumbnail_text TEXT,
    video_path TEXT,
    thumb_path TEXT,
    preview_path TEXT,
    status TEXT NOT NULL,                  -- pending | uploading | scheduled | published | rejected | failed
    youtube_id TEXT,
    publish_at TEXT,
    views INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    privacy TEXT,
    stats_updated_at TEXT,
    last_reminder_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS compilation_tracks (
    video_id INTEGER NOT NULL REFERENCES videos(id),
    track_id INTEGER NOT NULL REFERENCES tracks(id),
    position INTEGER NOT NULL,
    start_sec REAL NOT NULL,
    PRIMARY KEY (video_id, position)
);

CREATE TABLE IF NOT EXISTS stock_used (
    provider_id TEXT PRIMARY KEY,          -- Pexels "v123" / "p456": aynı klip tekrar kullanılmasın
    theme TEXT,
    used_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self.tx() as c:
            c.executescript(SCHEMA)
            cols = {r[1] for r in c.execute("PRAGMA table_info(tracks)")}
            if "theme" not in cols:  # eski veritabanları için
                c.execute("ALTER TABLE tracks ADD COLUMN theme TEXT")

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # --- settings -----------------------------------------------------
    def get_setting(self, key: str) -> str:
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        if row:
            return row["value"]
        return default_settings().get(key, "")

    def get_int(self, key: str) -> int:
        return int(self.get_setting(key))

    def set_setting(self, key: str, value: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # --- tracks -------------------------------------------------------
    def add_track(self, **fields: Any) -> int:
        fields.setdefault("created_at", iso(utcnow()))
        return self._insert("tracks", fields)

    def update_track(self, track_id: int, **fields: Any) -> None:
        self._update("tracks", track_id, fields)

    def track(self, track_id: int) -> sqlite3.Row:
        row = self.one("SELECT * FROM tracks WHERE id = ?", (track_id,))
        if row is None:
            raise KeyError(f"track {track_id} yok")
        return row

    # --- videos -------------------------------------------------------
    def add_video(self, **fields: Any) -> int:
        fields.setdefault("created_at", iso(utcnow()))
        if isinstance(fields.get("tags"), list):
            fields["tags"] = json.dumps(fields["tags"])
        return self._insert("videos", fields)

    def update_video(self, video_id: int, **fields: Any) -> None:
        if isinstance(fields.get("tags"), list):
            fields["tags"] = json.dumps(fields["tags"])
        self._update("videos", video_id, fields)

    def video(self, video_id: int) -> sqlite3.Row:
        row = self.one("SELECT * FROM videos WHERE id = ?", (video_id,))
        if row is None:
            raise KeyError(f"video {video_id} yok")
        return row

    def children(self, video_id: int) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM videos WHERE parent_id = ? ORDER BY id", (video_id,))

    def pending(self) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM videos WHERE parent_id IS NULL AND (status = 'pending' OR id IN "
            "(SELECT parent_id FROM videos WHERE status = 'pending' AND parent_id IS NOT NULL)) ORDER BY id"
        )

    # --- internals ----------------------------------------------------
    def _insert(self, table: str, fields: dict[str, Any]) -> int:
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self.tx() as c:
            cur = c.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(fields.values()))
            return int(cur.lastrowid)

    def _update(self, table: str, row_id: int, fields: dict[str, Any]) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.tx() as c:
            c.execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*fields.values(), row_id))


def tags_of(row: sqlite3.Row) -> list[str]:
    return json.loads(row["tags"]) if row["tags"] else []
