# db.py
"""
Database helper (SQLite) - create DB, add/list/delete/mark notified.
"""
import sqlite3
from typing import Optional, List, Dict
from contextlib import closing

DB_PATH = "events.db"

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            location TEXT,
            reminder_minutes INTEGER DEFAULT 0,
            notified INTEGER DEFAULT 0
        );
        """)
        conn.commit()

def add_event(event: str, start_time: str, end_time: Optional[str], location: Optional[str], reminder_minutes: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO events (event, start_time, end_time, location, reminder_minutes, notified)
        VALUES (?, ?, ?, ?, ?, 0)
        """, (event, start_time, end_time, location, reminder_minutes))
        conn.commit()
        return cur.lastrowid

def list_events() -> List[Dict]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM events ORDER BY start_time")
        rows = cur.fetchall()
        return [dict(r) for r in rows]

def mark_notified(event_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE events SET notified = 1 WHERE id = ?", (event_id,))
        conn.commit()

def delete_event(event_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
