"""HelixDB storage layer.

Relational (SQLite) for the core structured records. Settings and the
configurable scoring framework are kept as JSON in a `meta` table so the
institution can edit them at runtime (SRS sections 17-18, 31-32).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from ..config.settings import DB_PATH, ensure_dirs

_LOCAL = threading.local()


def _conn() -> sqlite3.Connection:
    if not hasattr(_LOCAL, "conn"):
        ensure_dirs()
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _LOCAL.conn = conn
    return _LOCAL.conn


@contextmanager
def cursor() -> Iterator[sqlite3.Cursor]:
    conn = _conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'faculty',
    designation TEXT DEFAULT '',
    department TEXT DEFAULT '',
    specialisation TEXT DEFAULT '',
    email TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'Active',
    year INTEGER,
    description TEXT DEFAULT '',
    details TEXT DEFAULT '{}',
    authors TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    verification_status TEXT DEFAULT 'draft',
    score REAL DEFAULT 0,
    score_breakdown TEXT DEFAULT '{}',
    doi TEXT DEFAULT '',
    isbn TEXT DEFAULT '',
    patent_no TEXT DEFAULT '',
    funding_agency TEXT DEFAULT '',
    source TEXT DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_staff ON projects(staff_id);
CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type);
CREATE INDEX IF NOT EXISTS idx_projects_verification ON projects(verification_status);
CREATE INDEX IF NOT EXISTS idx_projects_title ON projects(title);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'Seminar',
    description TEXT DEFAULT '',
    created_by TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS social (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workload (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id TEXT NOT NULL,
    month TEXT NOT NULL,
    total_hours INTEGER DEFAULT 0,
    teaching INTEGER DEFAULT 0,
    research INTEGER DEFAULT 0,
    administration INTEGER DEFAULT 0,
    UNIQUE(staff_id, month)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,
    resource TEXT DEFAULT '',
    resource_id TEXT DEFAULT '',
    detail TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db() -> None:
    with cursor() as cur:
        cur.executescript(SCHEMA)
    seed_defaults()


def get_meta(key: str, default: Any = None) -> Any:
    with cursor() as cur:
        row = cur.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except Exception:
        return default


def set_meta(key: str, value: Any) -> None:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, default=str)),
        )


def seed_defaults() -> None:
    """Insert institutional defaults if the meta table is empty."""
    from ..config.settings import load_default_scoring

    if get_meta("college_config") is None:
        set_meta(
            "college_config",
            {
                "name": "Global Tech University",
                "logo": "institution-logo",
                "email": "research@gtu.edu.ac",
                "address": "Global Tech Campus, Innovation District",
                "phone": "",
                "research_cell": "Office of Research, Innovation & Transfer",
                "tagline": "Aggregate first, verify second, analyse third, infer last.",
            },
        )
    if get_meta("scoring_config") is None:
        set_meta("scoring_config", load_default_scoring())
    if get_meta("database_config") is None:
        set_meta("database_config", {"enabled": False, "apiBaseUrl": "/api", "dbName": "researchmitra"})
    if get_meta("backup_config") is None:
        set_meta(
            "backup_config",
            {
                "enabled": True,
                "scheduled": False,
                "interval_days": 7,
                "retention": 10,
                "last_backup": None,
                "path": str(DB_PATH.parent / "backups"),
            },
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for key in ("details", "authors", "metadata", "score_breakdown"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = {} if key != "authors" else []
    return d


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(r) for r in rows if r is not None]


def now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()
