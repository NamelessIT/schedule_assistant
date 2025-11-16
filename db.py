# db.py
"""
SQLite DB helper for schedule assistant.
Includes support fields:
- next_notify (ISO string)
- repeat (text: 'daily'|'weekly'|'monthly' or NULL)
- pending_auto_mark (0/1)
"""
import sqlite3
from typing import Optional, List, Dict
from contextlib import closing
from dateutil import parser as dateparser
from datetime import timedelta
import pytz

DB_PATH = "events.db"
LOCAL_TZ = pytz.timezone("Asia/Ho_Chi_Minh")


def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT DEFAULT NULL,
            location TEXT,
            reminder_minutes INTEGER DEFAULT 15,
            notified INTEGER DEFAULT 0,
            importance TEXT DEFAULT 'normal',
            repeat_count INTEGER DEFAULT 0,
            isStop INTEGER DEFAULT 0,
            next_notify TEXT DEFAULT NULL,
            repeat TEXT DEFAULT NULL,
            pending_auto_mark INTEGER DEFAULT 0
        );
        """)
        conn.commit()
        # try to add missing columns safely (no-op if exists)
        try:
            cur.execute("ALTER TABLE events ADD COLUMN next_notify TEXT DEFAULT NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE events ADD COLUMN repeat TEXT DEFAULT NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE events ADD COLUMN pending_auto_mark INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def _compute_next_notify_iso(start_time_iso: str, reminder_minutes: int) -> Optional[str]:
    """
    Compute start_time - reminder_minutes, floor seconds to 0, return ISO with tz.
    """
    try:
        dt = dateparser.isoparse(start_time_iso)
        if dt.tzinfo is None:
            dt = LOCAL_TZ.localize(dt)
        next_dt = dt - timedelta(minutes=int(reminder_minutes or 0))
        # floor seconds/microseconds
        next_dt = next_dt.replace(second=0, microsecond=0)
        next_dt = next_dt.astimezone(LOCAL_TZ)
        return next_dt.isoformat()
    except Exception:
        return None


def add_event(event: str, start_time: str, end_time: Optional[str], location: Optional[str],
              reminder_minutes: int, repeat: Optional[str] = None) -> int:
    """
    Insert event and compute next_notify. Returns inserted row id.
    """
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO events (event, start_time, end_time, location, reminder_minutes, notified, repeat)
        VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (event, start_time, end_time, location, reminder_minutes, repeat))
        conn.commit()
        rowid = cur.lastrowid

        next_iso = _compute_next_notify_iso(start_time, reminder_minutes)
        if next_iso:
            cur.execute("UPDATE events SET next_notify = ? WHERE id = ?", (next_iso, rowid))
            conn.commit()

        return rowid


def get_event(event_id: int) -> Optional[Dict]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_events() -> List[Dict]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM events ORDER BY start_time")
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def mark_notified(event_id: int):
    """
    Mark event as notified and clear next_notify/pending_auto_mark.
    For repeating events, reminder loop will handle rescheduling.
    """
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE events SET notified = 1, next_notify = NULL, pending_auto_mark = 0 WHERE id = ?", (event_id,))
        conn.commit()


def delete_event(event_id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()


def update_event_field(event_id, field, value):
    allowed = {"event", "start_time", "end_time", "location", "reminder_minutes",
               "notified", "importance", "repeat_count", "isStop", "next_notify",
               "repeat", "pending_auto_mark"}
    if field not in allowed:
        raise ValueError(f"Field {field} not allowed to update.")
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE events SET {field} = ? WHERE id = ?", (value, event_id))
        conn.commit()
