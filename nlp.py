# nlp.py (v6.1) — fixed event-name extraction for patterns like:
# "5 phút nữa tui muốn họp nhóm, nhắc tui trước 3 phút"

import re
from typing import Optional, Dict
from datetime import datetime, timedelta, date, time
from dateutil import parser as dateparser
import pytz

# Optional Underthesea
try:
    from underthesea import ner as under_ner
    HAS_UNDER = True
except:
    HAS_UNDER = False

LOCAL_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# -------------------------------------
# VN number map
# -------------------------------------
VN_NUM = {
    "không":0, "một":1, "mốt":1, "hai":2, "ba":3, "bốn":4, "tư":4,
    "năm":5, "sáu":6, "bảy":7, "tám":8, "chín":9,
    "mười":10, "mười một":11, "mười hai":12, "mười ba":13,
    "mười bốn":14, "mười lăm":15, "mười sáu":16, "mười bảy":17,
    "mười tám":18, "mười chín":19,
    "hai mươi":20, "hai mươi mốt":21, "hai mươi hai":22, "hai mươi ba":23
}

def replace_vn_num(s: str) -> str:
    s2 = s.lower()
    for k in sorted(VN_NUM.keys(), key=len, reverse=True):
        s2 = re.sub(rf"\b{k}\b", str(VN_NUM[k]), s2)
    return s2

# -------------------------------------
# normalize
# -------------------------------------
def norm(text: str) -> str:
    t = text.strip().lower()
    t = replace_vn_num(t)
    t = t.replace("giờ", "h")
    t = t.replace(".", ":")
    t = re.sub(r"[,;()]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = LOCAL_TZ.localize(dt)
    else:
        dt = dt.astimezone(LOCAL_TZ)
    return dt.replace(microsecond=0).isoformat()

# -------------------------------------
# reminder extraction
# -------------------------------------
def extract_reminder(text: str) -> int:
    m = re.search(r"nhắc(?: tôi| tui)?\s*(?:trước)?\s*(\d+)\s*(phút|p|giờ|g|ngày)?", text)
    if not m:
        return 15
    n = int(m.group(1))
    unit = m.group(2) or "phút"
    if "ngày" in unit: return n * 1440
    if "giờ" in unit or unit == "g": return n * 60
    return n

# -------------------------------------
# relative minutes/hours
# -------------------------------------
def get_rel_minutes(t: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*(phút|p)\s*nữa", t)
    return int(m.group(1)) if m else None

def get_rel_hours(t: str) -> Optional[int]:
    m = re.search(r"(\d+)\s*(giờ|h)\s*nữa", t)
    return int(m.group(1)) if m else None

# -------------------------------------
# location
# -------------------------------------
def extract_location(text: str) -> Optional[str]:
    if HAS_UNDER:
        try:
            ents = under_ner(text)
            buf = []
            locs = []
            for tok, tag in ents:
                if tag in ("LOC", "B-LOC", "I-LOC"):
                    buf.append(tok)
                else:
                    if buf:
                        locs.append(" ".join(buf)); buf = []
            if buf: locs.append(" ".join(buf))
            if locs: return locs[0]
        except:
            pass
    m = re.search(r"\b(?:ở|tại)\s+([^,.;]+)", text)
    if m:
        loc = m.group(1).strip()
        loc = re.sub(r"(nhé|giúp|giùm).*", "", loc).strip()
        return loc
    return None

# -------------------------------------
# time explicit
# -------------------------------------
def extract_time(t: str):
    m = re.search(r"\b(\d{1,2})[:h](\d{1,2})\b", t)
    if m: return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"\b(\d{1,2})h\b", t)
    if m2: return int(m2.group(1)), 0
    return None

# -------------------------------------
# date logic
# -------------------------------------
WEEKDAY = {
    "hai":0,"thứ hai":0,"th2":0,"thứ 2":0,
    "ba":1,"thứ ba":1,"th3":1,"thứ 3":1,
    "tư":2,"thứ tư":2,"th4":2,"thứ 4":2,
    "năm":3,"thứ năm":3,"th5":3,"thứ 5":3,
    "sáu":4,"thứ sáu":4,"th6":4,"thứ 6":4,
    "bảy":5,"thứ bảy":5,"th7":5,"thứ 7":5,
    "chủ nhật":6,"cn":6,"chủ n":6,"thứ chủ nhật":6,"thứ cn":6,"thứ 8":6 
}

def extract_date(t: str) -> Optional[date]:
    today = datetime.now(LOCAL_TZ).date()
    if "hôm nay" in t: return today
    if "mai" in t: return today + timedelta(days=1)
    if "mốt" in t: return today + timedelta(days=2)
    m = re.search(r"(\d+)\s*ngày nữa", t)
    if m: return today + timedelta(days=int(m.group(1)))
    for k, wd in WEEKDAY.items():
        if k in t:
            cur = today.weekday()
            delta = (wd - cur + 7) % 7
            if delta == 0: delta = 7
            return today + timedelta(days=delta)
    m = re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
    if m:
        d = int(m.group(1)); mo = int(m.group(2))
        y = m.group(3)
        if y:
            y = int(y); 
            if y < 100: y += 2000
        else:
            y = today.year
        try:
            return date(y, mo, d)
        except:
            return None
    return None

# -------------------------------------
# repeat detection
# -------------------------------------
def extract_repeat(t: str) -> Optional[str]:
    if re.search(r"(mỗi ngày|hàng ngày|daily)", t): return "daily"
    if re.search(r"(mỗi tuần|hàng tuần|weekly|mỗi thứ)", t): return "weekly"
    if re.search(r"(mỗi tháng|hàng tháng|monthly)", t): return "monthly"
    return None

# -------------------------------------
# improved event name extraction
# -------------------------------------
def extract_event_candidate_from_intent(t_raw: str) -> Optional[str]:
    """
    Try to capture patterns where user says 'muốn/cần/định/đặt/hãy' after a relative time.
    e.g. '5 phút nữa tui muốn họp nhóm, nhắc tui trước 3 phút' ->
          capture 'họp nhóm'
    Return None if not found.
    """
    # Normalize spaces and commas
    s = re.sub(r"\s+", " ", t_raw).strip()
    # Patterns to detect verbs expressing intent
    patterns = [
        r"(?:^|\b)(?:tôi|tui|mình)?\s*(?:muốn|cần|muốn được|định|muốn tổ chức|muốn họp|đặt|hãy|giúp)\s+(.*?)(?:,|nhắc|lúc|ở|tại|$)",
        r"(?:^|\b)(?:tôi|tui|mình)?\s*(.*?)(?:,|nhắc|lúc|ở|tại|$)"  # fallback broad capture
    ]
    for p in patterns:
        m = re.search(p, s)
        if m:
            cand = m.group(1).strip()
            # remove leading pronouns if still present
            cand = re.sub(r"^(tôi|tui|mình)\s+", "", cand).strip()
            # remove trailing residual 'tui' or 'tôi'
            cand = re.sub(r"\s+(tui|tôi)$", "", cand).strip()
            # if candidate is not empty and not just words like 'nhắc' keep it
            if cand and len(cand) <= 120:
                # remove phrases that look like reminders or time words
                cand = re.sub(r"\b(nhắc|trước|phút|giờ|h|ngày|lúc|ở|tại)\b.*", "", cand).strip()
                if cand:
                    return cand
    return None

def clean_event_name(t: str) -> str:
    """
    t is a preprocessed text (lowercased, numbers replaced)
    Use multiple strategies:
    1) Try intent-capture function (muốn / cần / hãy ...)
    2) Fallback: remove common noise words and time/location fragments
    """
    # 1) direct intent capture
    cand = extract_event_candidate_from_intent(t)
    if cand:
        # final cleanup
        s = cand
        s = re.sub(r"\b(sự kiện)\b", "", s)
        s = re.sub(r"\b(tui|tôi|mình)\b", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            return s

    # 2) fallback cleaning
    s = t
    s = re.sub(r"\b(nhắc|nhắc tôi|nhắc tui|tạo|tạo cho tôi|tạo cho tui|sự kiện|hãy|giúp)\b", "", s)
    s = re.sub(r"\d+\s*(phút|giờ|p|g)\s*nữa", "", s)
    s = re.sub(r"nhắc.*trước.*", "", s)
    s = re.sub(r"\blúc\b.*", "", s)
    s = re.sub(r"(ở|tại)\s+[^,.;]+", "", s)
    s = re.sub(r"(hôm nay|mai|mốt|sáng|trưa|chiều|tối|đêm)", "", s)
    s = re.sub(r"\d{1,2}[:h]\d{0,2}", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else "Sự kiện"

# -------------------------------------
# main parse
# -------------------------------------
def parse_text(text: str) -> Optional[Dict]:
    if not text or not text.strip():
        return None

    raw = text
    t = norm(raw)
    now = datetime.now(LOCAL_TZ)

    # relative time
    rel_min = get_rel_minutes(t)
    rel_hr  = get_rel_hours(t)

    dt_start = None
    dt_end = None

    if rel_min:
        dt_start = now + timedelta(minutes=rel_min)
    elif rel_hr:
        dt_start = now + timedelta(hours=rel_hr)

    # remove relative fragment for reminder and name extraction
    t_no_relative = re.sub(r"\d+(phút|giờ|p|g)\s*nữa", "", t)
    reminder = extract_reminder(t_no_relative)

    # repeat detection
    repeat = extract_repeat(t)

    # location (use raw to preserve punctuation/casing for NER)
    location = extract_location(raw)

    # explicit time handling
    if not dt_start:
        tm = extract_time(t)
        if tm:
            h, m = tm
            d = extract_date(t) or now.date()
            dt_start = datetime.combine(d, time(h, m))
        else:
            # fallback to dateparser
            try:
                dt_start = dateparser.parse(raw, languages=["vi"], default=now)
            except:
                dt_start = None

    if not dt_start:
        return None

    # localize if naive
    if dt_start.tzinfo is None:
        dt_start = LOCAL_TZ.localize(dt_start)
    dt_start = dt_start.replace(second=0, microsecond=0)

    # if user likely meant next day
    if dt_start < now - timedelta(seconds=5):
        dt_start += timedelta(days=1)

    # EVENT NAME: use t_no_relative but prefer intent-capture that handles "muốn/cần/..."
    event_name = clean_event_name(t_no_relative)

    # importance detection
    importance = "normal"
    if re.search(r"\b(quan trọng|important|ưu tiên)\b", t):
        importance = "important"
    if re.search(r"\b(cực quan trọng|rất quan trọng|khẩn cấp|urgent)\b", t):
        importance = "critical"

    result = {
        "event": event_name,
        "start_time": to_iso(dt_start),
        "end_time": None,
        "location": location,
        "reminder_minutes": reminder,
        "importance": importance,
        "repeat": repeat,
        "repeat_count": 0,
        "notified": 0,
        "isStop": 0
    }
    return result

# quick test harness (run as script)
if __name__ == "__main__":
    cases = [
        "5 phút nữa tui muốn họp nhóm, nhắc tui trước 3 phút",
        "Nhắc tui 5 phút nữa đi học, nhắc trước 1 phút",
        "Nhắc tôi họp nhóm lúc mười giờ sáng mai ở phòng 302",
    ]
    for c in cases:
        print("INPUT:", c)
        print("OUTPUT:", parse_text(c))
        print("------")
