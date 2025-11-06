# export.py
"""
Export functions: JSON and ICS (iCalendar).
"""
import json
from ics import Calendar, Event
from db import list_events
from dateutil import parser

def export_json(path="events_export.json"):
    events = list_events()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    return path

def export_ics(path="events_export.ics"):
    cal = Calendar()
    events = list_events()
    for ev in events:
        e = Event()
        e.name = ev.get("event") or ""
        try:
            e.begin = parser.isoparse(ev["start_time"])
            if ev.get("end_time"):
                e.end = parser.isoparse(ev["end_time"])
        except Exception:
            # ignore parse errors
            pass
        e.location = ev.get("location") or ""
        cal.events.add(e)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(cal)
    return path
