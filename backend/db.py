
"""SQLite storage. Raw files are processed in memory; only user-approved text is saved."""
from __future__ import annotations

import json
import hashlib
from contextvars import ContextVar
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv('CAREER_DB_PATH', str(Path(__file__).parent / 'data' / 'career.db')))
_VISITOR_ID: ContextVar[str | None] = ContextVar('career_visitor_id', default=None)


def set_current_visitor(visitor_id: str):
    return _VISITOR_ID.set(visitor_id)


def reset_current_visitor(token):
    _VISITOR_ID.reset(token)


def current_db_path() -> Path:
    visitor = _VISITOR_ID.get()
    if visitor is None:
        return DB_PATH
    # Never allow a visitor-supplied value to become a filesystem path.
    hashed = hashlib.sha256(visitor.encode('utf-8')).hexdigest()
    return DB_PATH.parent / 'visitors' / f'{hashed}.db'


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def connection():
    path = current_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS experiences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, organization TEXT NOT NULL DEFAULT '',
            experience_type TEXT NOT NULL DEFAULT 'other', parent_experience_id INTEGER,
            period TEXT NOT NULL DEFAULT '', background TEXT NOT NULL DEFAULT '',
            task TEXT NOT NULL DEFAULT '', actions TEXT NOT NULL DEFAULT '',
            methods TEXT NOT NULL DEFAULT '', results TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL DEFAULT '', skills TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft', source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, company TEXT NOT NULL DEFAULT '', raw_text TEXT NOT NULL,
            requirements TEXT NOT NULL DEFAULT '[]', mode TEXT NOT NULL DEFAULT 'demo',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, jd_id INTEGER NOT NULL,
            data TEXT NOT NULL, match_data TEXT NOT NULL, mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (jd_id) REFERENCES jds(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, story_id INTEGER NOT NULL,
            messages TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
            FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT NOT NULL,
            mode TEXT NOT NULL, success INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        ''')
        # Backward-compatible migration for existing local databases.
        columns = {row['name'] for row in db.execute('PRAGMA table_info(experiences)').fetchall()}
        if 'experience_type' not in columns:
            db.execute("ALTER TABLE experiences ADD COLUMN experience_type TEXT NOT NULL DEFAULT 'other'")
        if 'parent_experience_id' not in columns:
            db.execute('ALTER TABLE experiences ADD COLUMN parent_experience_id INTEGER')


def one(table: str, record_id: int):
    assert table in {'experiences', 'jds', 'stories', 'interviews'}
    with connection() as db:
        row = db.execute(f'SELECT * FROM {table} WHERE id = ?', (record_id,)).fetchone()
        return dict(row) if row else None


def all_rows(table: str):
    assert table in {'experiences', 'jds', 'stories', 'interviews'}
    with connection() as db:
        return [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY id DESC').fetchall()]


def add_run(operation: str, mode: str, success: bool):
    with connection() as db:
        db.execute('INSERT INTO agent_runs (operation,mode,success,created_at) VALUES (?,?,?,?)', (operation, mode, int(success), utc_now()))


def decode(row: dict | None):
    if row is None:
        return None
    row = dict(row)
    for key in ('skills', 'requirements', 'data', 'match_data', 'messages'):
        if key in row and isinstance(row[key], str):
            row[key] = json.loads(row[key])
    return row
