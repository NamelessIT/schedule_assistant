# nlp.py
"""
Rule-based NLP parser for Vietnamese scheduling phrases.
Function: parse_text(text) -> dict or None

Outputs dict:
{
  "event": str,
  "start_time": ISO string (e.g. "2025-11-01T10:00:00"),
  "end_time": Optional ISO string,
  "location": Optional str,
  "reminder_minutes": int (default 15)
  "repeat": Optional str (e.g. "weekly")
}
"""
import re
from typing import Optional, Dict
from datetime import datetime, timedelta, time, date
from dateutil import parser as dateparser
import pytz

WEEKDAY_MAP = {
    "hai": 0, "thứ hai": 0, "th2": 0, "thứ 2": 0, "t2": 0,
    "ba": 1, "thứ ba": 1, "th3": 1, "thứ 3": 1,
    "tư": 2, "thứ tư": 2, "th4": 2, "thứ 4": 2,
    "năm": 3, "thứ năm": 3, "th5": 3, "thứ 5": 3,
    "sáu": 4, "thứ sáu": 4, "th6": 4, "thứ 6": 4,
    "bảy": 5, "thứ bảy": 5, "th7": 5, "thứ 7": 5,
    "chủ nhật": 6, "cn": 6, "chủnhật": 6
}

def _norm(text: str) -> str:
    t = text.strip().lower()
    t = t.replace("giờ", "h")
    t = t.replace(".", ":")
    t = re.sub(r"\s+", " ", t)
    return t

def _extract_reminder(text: str) -> int:
    # examples: "nhắc trước 10 phút", "nhắc 15p", "nhắc trước 1 ngày"
    m = re.search(r"nhắc(?: trước)?\s*([0-9]+)\s*(phút|p|phút|ph|giờ|g|ngày|ngày)", text)
    if not m:
        return 15  # default
    num = int(m.group(1))
    unit = m.group(2)
    if "ngày" in unit:
        return num * 24 * 60
    if "giờ" in unit or unit in ("g","ph"):
        return num * 60
    # minutes default
    return num

def _extract_location(text: str) -> Optional[str]:
    # look for "ở <location>" or "tại <location>"
    m = re.search(r"\b(?:ở|tại)\s+([^\.,;:]+)", text)
    if m:
        loc = m.group(1).strip()
        # remove trailing words like 'nhé' or ' nhé'
        loc = re.sub(r"\b(nhé| nhé|giúp|giùm)\b.*", "", loc).strip()
        return loc
    return None

def _extract_time_simple(text: str):
    """
    Find time like '10h', '10:30', '19:30', '10 giờ sáng', '7h30 tối'
    Returns tuple (hour:int, minute:int, modifier:str|'am'/'pm'/'morning'/'evening'/None)
    """
    # direct HH:MM or H:MM
    m = re.search(r"(\d{1,2})\s*[:h]\s*(\d{1,2})\b", text)
    if m:
        h = int(m.group(1))
        mnt = int(m.group(2))
        # look for period modifiers
        if re.search(r"\bsáng\b", text):
            mod = "morning"
        elif re.search(r"\b(trưa|chiều|tối)\b", text):
            mod = "afternoon"
        else:
            mod = None
        return h, mnt, mod
    # only hour like 10h or 10 giờ or 10
    m2 = re.search(r"\b(\d{1,2})\s*(?:h|giờ|g)\b", text)
    if m2:
        h = int(m2.group(1))
        mnt = 0
        if re.search(r"\bsáng\b", text):
            mod = "morning"
        elif re.search(r"\b(trưa|chiều|tối)\b", text):
            mod = "afternoon"
        else:
            mod = None
        return h, mnt, mod
    return None

def _extract_date_explicit(text: str) -> Optional[datetime]:
    # formats: dd/mm/yyyy or dd/mm or yyyy-mm-dd
    m = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", text)
    if m:
        d = int(m.group(1))
        mo = int(m.group(2))
        y = m.group(3)
        if y:
            yy = int(y)
            if yy < 100:  # e.g. 25 -> 2025 assumption
                yy += 2000
        else:
            yy = datetime.now().year
        try:
            return datetime(year=yy, month=mo, day=d)
        except Exception:
            return None
    # ISO-like yyyy-mm-dd
    m2 = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m2:
        yy = int(m2.group(1)); mo = int(m2.group(2)); d = int(m2.group(3))
        try:
            return datetime(year=yy, month=mo, day=d)
        except Exception:
            return None
    return None

def _extract_relative_date(text: str) -> Optional[date]:
    today = datetime.now().date()
    if re.search(r"\bhôm nay\b", text):
        return today
    if re.search(r"\bmai\b", text) or re.search(r"\bngày mai\b", text):
        return today + timedelta(days=1)
    if re.search(r"\bngày mốt\b", text) or re.search(r"\bmốt\b", text):
        return today + timedelta(days=2)
    # weekend
    if re.search(r"cuối tuần", text):
        # next saturday
        dow = today.weekday()
        days_ahead = (5 - dow) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)
    # weekdays "thứ hai", "thứ ba", ...
    for key, wd in WEEKDAY_MAP.items():
        if key in text:
            # compute next date with weekday wd
            dow = today.weekday()
            days_ahead = (wd - dow + 7) % 7
            if days_ahead == 0:
                days_ahead = 7  # next week
            return today + timedelta(days=days_ahead)
    return None

def _extract_time_range(text: str):
    # matches "14:00 - 15:30" or "14:00-15:30"
    m = re.search(r"(\d{1,2}[:h]\s*\d{0,2})\s*[-–]\s*(\d{1,2}[:h]\s*\d{0,2})", text)
    if m:
        s1 = m.group(1).replace("h", ":").replace(" ", "")
        s2 = m.group(2).replace("h", ":").replace(" ", "")
        try:
            t1 = dateparser.parse(s1)
            t2 = dateparser.parse(s2)
            return t1.time(), t2.time()
        except Exception:
            return None
    return None

def _to_iso(dt_obj: datetime) -> str:
    # produce ISO without timezone (or .isoformat())
    return dt_obj.replace(microsecond=0).isoformat()

def parse_text(text: str) -> Optional[Dict]:
    """
    Main entry. Returns dict or None.
    """
    if not text or not text.strip():
        return None
    t = _norm(text)
    reminder = _extract_reminder(t)
    location = _extract_location(t)

    # default event name: remove time/location parts heuristically
    # We'll attempt to remove "nhắc ...", "ở ...", "tại ..." and time/date patterns
    event_name = t
    # cut location phrase
    event_name = re.sub(r"\b(?:ở|tại)\s+[^\.,;:]+", "", event_name)
    # cut reminder phrase
    event_name = re.sub(r"nhắc(?: trước)?\s*[0-9]+\s*(phút|p|giờ|ngày)?", "", event_name)
    # cut known keywords 'nhắc tôi' -> ''
    event_name = re.sub(r"\b(nhắc tôi|nhắc)\b", "", event_name)
    # cut time expressions
    event_name = re.sub(r"\b\d{1,2}[:h]\s*\d{0,2}\b", "", event_name)
    event_name = re.sub(r"\b\d{1,2}\s*(?:h|giờ|g)\b", "", event_name)
    event_name = re.sub(r"\b(hôm nay|mai|ngày mai|ngày mốt|mốt|cuối tuần)\b", "", event_name)
    event_name = re.sub(r"\b(thứ|th)\s*\d\b", "", event_name)
    event_name = re.sub(r"[-–:]", " ", event_name)
    event_name = re.sub(r"\s+", " ", event_name).strip()
    # fallback: if empty, put generic "Sự kiện"
    if not event_name:
        event_name = "Sự kiện"

    # 1) explicit date
    explicit_date = _extract_date_explicit(t)
    rel_date = _extract_relative_date(t)

    # 2) time
    time_info = _extract_time_simple(t)
    # 3) time range
    time_range = _extract_time_range(text)

    # decide date_to_use
    now = datetime.now()
    if explicit_date:
        date_part = explicit_date.date()
    elif rel_date:
        date_part = rel_date
    else:
        # if no date mentioned but time exists, assume today or next occurrence if time passed
        date_part = now.date()

    # handle time
    if time_info:
        hour, minute, mod = time_info
        # adjust mod morning/afternoon heuristic
        if mod == "morning":
            if 1 <= hour <= 5:
                hour += 12  # sometimes '1' morning? keep as is. This is heuristic; prefer keep.
        elif mod == "afternoon":
            if 1 <= hour <= 11:
                # afternoon or evening -> add 12 if hour <=11 and hour<12
                if hour < 12:
                    hour = (hour % 12) + 12
        # build datetime
        try:
            dt_start = datetime.combine(date_part, time(hour=hour, minute=minute))
        except Exception:
            # fallback: parse via dateutil with combined string
            try:
                dt_start = dateparser.parse(f"{date_part.isoformat()} {hour}:{minute}")
            except Exception:
                dt_start = None
    else:
        # no time found: if phrase contains "cả ngày" -> set time 09:00 as default or 00:00
        if re.search(r"cả ngày", t):
            dt_start = datetime.combine(date_part, time(hour=9, minute=0))
        else:
            dt_start = None

    # end time if time_range present
    dt_end = None
    if time_range and dt_start:
        t1, t2 = time_range
        try:
            dt_end = datetime.combine(date_part, t2)
        except Exception:
            dt_end = None

    # if no explicit date/time but phrase like "15/11/2025 14:00 - 15:30" dateparser can parse entire string
    if dt_start is None:
        try:
            parsed = dateparser.parse(text, default=now)
            if parsed:
                dt_start = parsed
        except Exception:
            dt_start = None

    if dt_start:
        # convert to ISO (naive) - you may want to convert to timezone-aware in production
        start_iso = _to_iso(dt_start)
        end_iso = _to_iso(dt_end) if dt_end else None
    else:
        # cannot parse time -> return None (or create with default now + 1 hour?)
        return None

    result = {
        "event": event_name.strip(),
        "start_time": start_iso,
        "end_time": end_iso,
        "location": location,
        "reminder_minutes": int(reminder)
    }

    return result

# For quick manual test
if __name__ == "__main__":
    tests = [
        "Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302",
        "Tối mai 19:30 gặp Tùng tại quán cà phê, nhắc trước 10 phút",
        "Họp dự án 15/11/2025 14:00 - 15:30, phòng 101, nhắc trước 30 phút",
        "Sinh nhật Lan ngày 20/12 (cả ngày), nhắc trước 1 ngày",
        "Tập gym mỗi thứ Hai lúc 18h"
    ]
    for s in tests:
        print("INPUT:", s)
        print("PARSE:", parse_text(s))
        print("----")
