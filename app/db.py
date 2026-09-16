from pathlib import Path
import sqlite3
import json

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DB_PATH = ROOT / CONFIG["database"]

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_column(conn, table, column, definition):
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def init_db():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            description TEXT,
            source_url TEXT UNIQUE,
            salary TEXT,
            source TEXT,
            source_job_id TEXT,
            publication_date TEXT,
            match_score INTEGER DEFAULT 0,
            recommended_resume TEXT,
            recommendation TEXT,
            resume_scores_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'review',
            notes TEXT,
            applied_at TEXT,
            interview_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS gmail_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_message_id TEXT NOT NULL UNIQUE,
            thread_id TEXT,
            job_id INTEGER,
            sender TEXT,
            subject TEXT,
            event_type TEXT,
            received_at TEXT,
            snippet TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS discovery_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            fetched_total INTEGER,
            unique_total INTEGER,
            query_matched INTEGER,
            title_rejected INTEGER DEFAULT 0,
            location_excluded INTEGER,
            blocked_seniority INTEGER,
            below_score INTEGER,
            qualified INTEGER,
            saved INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        _ensure_column(conn, "discovery_runs", "title_rejected", "INTEGER DEFAULT 0")
        _ensure_column(conn, "jobs", "application_url", "TEXT")
        _ensure_column(conn, "jobs", "route_type", "TEXT")
        _ensure_column(conn, "jobs", "automation_status", "TEXT")
        conn.commit()
