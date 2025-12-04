# nlp.py v8.1
# - Fix: không remove_diacritics trước khi parse time/date (không phá dateparser)
# - Improved ASCII/no-diacritics mapping (works for spaced phrases and no-diacritics input)
# - Single clean_event_name implementation (no duplicates)
# - Better handling of natural time phrases (tầm chiều, cuối tuần...)
# - Keep remove_diacritics for intent/event-name & location extraction only

import re
import unicodedata
from typing import Optional, Dict
from datetime import datetime, timedelta, time, date
from dateutil import parser as dateparser
import pytz

LOCAL_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# -------------------------
# Helpers
# -------------------------
def remove_diacritics(s: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = LOCAL_TZ.localize(dt)
    else:
        dt = dt.astimezone(LOCAL_TZ)
    return dt.replace(microsecond=0).isoformat()

# -------------------------
# ASCII / shorthand maps
# -------------------------
# Keep keys lowercased, include both accented and non-accented forms via code below.
ASCII_MAP = {
    # times / shorthand
    "gio": "giờ", "g": "giờ", "h": "giờ",
    "phut": "phút", "ph": "phút", "p": "phút",

    # time-of-day
    "sang": "sáng", "trua": "trưa", "chieu": "chiều", "toi": "tối", "dem": "đêm",

    # verbs/pronouns
    "tui": "tui", "toi": "tôi", "minh": "mình",
    "tao": "tạo", "tao ra": "tạo", "tao cho": "tạo cho", "giup": "giúp", "hay": "hãy",

    # multi-word calendar phrases (use spaced keys too)
    "tuần sau": "tuần sau", "tuan sau": "tuần sau",
    "tuần tới": "tuần tới", "tuan toi": "tuần tới",
    "cuối tuần": "cuối tuần", "cuoi tuan": "cuối tuần",
    "giữa tuần": "giữa tuần", "giu a tuan": "giữa tuần", "dau tuần": "đầu tuần", "dau tuan": "đầu tuần",
    "tháng sau": "tháng sau", "thang sau": "tháng sau",

    "buoi sang": "sáng",
    "buoi trua": "trưa",
    "buoi chieu": "chiều",
    "buoi toi": "tối",
    "ban dem": "đêm",
    "khuya": "khuya",
    "som": "sớm",
    "toi nay": "tối nay",
    "sang nay": "sáng nay",
    "chieu nay": "chiều nay",
    "tois mai": "tối mai",
    "chieu mai": "chiều mai",
    "sang mai": "sáng mai",
    "ngay mai": "ngày mai",
    "ngay": "ngày",
    "ngay nua": "ngày nữa",
    "motngay": "một ngày",
    "motngaynua": "một ngày nữa",
    "mot ngay nua": "một ngày nữa",
    "ngay mot": "ngày mốt",    # khi bị chuyển không dấu
    "ngay mốt": "ngày mốt",
    "ngay mot": "ngày mốt",    # thêm dòng này để override lỗi


    "ngay hom nay": "hôm nay",
    "ngay mai": "mai",
    "ngay kia": "mốt",
    "motngay": "một ngày",
    "mot ngay ": "một ngày",
    "tuan nay": "tuần này",
    "tuan sau": "tuần sau",
    "tuan toi": "tuần tới",
    "tuan truoc": "tuần trước",
    "thang nay": "tháng này",
    "thang sau": "tháng sau",
    "thang toi": "tháng tới",
    "cuoi thang": "cuối tháng",
    "giua thang": "giữa tháng",
    "dau thang": "đầu tháng",
    "giua tuan": "giữa tuần",
    "cuoi tuan": "cuối tuần",

    "nhac": "nhắc",
    "nhac nho": "nhắc nhở",
    "bao": "bảo",
    "goi": "gọi",
    "lap": "lập",
    "hen": "hẹn",
    "dat": "đặt",
    "tao lich": "tạo lịch",
    "tao su kien": "tạo sự kiện",
    "them": "thêm",

    "nhacj": "nhắc",
    "nhawk": "nhắc",
    "nhacn": "nhắc",
    "thoigian": "thời gian",
    "nhacws": "nhắc",
    "phutj": "phút",
    "phutw": "phút",
    "gioj": "giờ",
    "phuts": "phút",
    "phut s": "phút",
    "giow": "giờ",
    "giowf": "giờ",
    "giof": "giờ",
    "gjo": "giờ",
    "pjut": "phút",
    "phujt": "phút",
    "luk": "lúc",
    "dk": "được",
    "hop": "họp",
    "hopj": "họp",
    "hopw": "họp",

    "di lam": "đi làm",
    "di hoc": "đi học",
    "di choi": "đi chơi",
    "gap": "gặp",
    "hen gap": "hẹn gặp",
    "hop": "họp",
    "hop nhom": "họp nhóm",
    "cf": "cà phê",
    "cafe": "cà phê",
    "truong": "trường",
    "quan": "quán",
}

# -------------------------
# Vietnamese number words -> digits
# -------------------------
VN_NUM = {
    "không":0, "mot":1, "một":1,
    "hai":2, "ba":3, "bốn":4, "bon":4, "tư":4,
    "năm":5, "nam":5, "sáu":6, "sau":6, "bay":7, "bảy":7, "tam":8, "tám":8,
    "chín":9, "chin":9, "muoi":10, "mười":10, "mười một":11, "muoi mot":11,
    "mười hai":12, "muoi hai":12,
    "muoi ba": 13,
    "muoi bon": 14,
    "muoi lam": 15,
    "muoi sau": 16,
    "muoi bay": 17,
    "muoi tam": 18,
    "muoi chin": 19,
    "hai muoi": 20,
    "hai muoi mot": 21,
    "hai muoi hai": 22,
    "hai muoi ba": 23,
    "ba muoi": 30,
    "bon muoi": 40,
    "nam muoi": 50,
    "sau muoi": 60,
}

def apply_ascii_map(s: str) -> str:
    """Apply ASCII_MAP robustly. Accept both normal and no-diacritics input."""
    txt = s
    # First handle larger/longer keys first (sort by length desc)
    keys = sorted(ASCII_MAP.keys(), key=lambda x: len(x), reverse=True)
    for k in keys:
        v = ASCII_MAP[k]
        # match both original key and its no-diacritics variant
        k_nd = remove_diacritics(k)
        # Replace occurrences with word boundary guard (avoid mid-word replacements)
        pattern1 = rf'(?<!\w){re.escape(k)}(?!\w)'
        pattern2 = rf'(?<!\w){re.escape(k_nd)}(?!\w)'
        txt = re.sub(pattern1, v, txt)
        if k_nd != k:
            txt = re.sub(pattern2, v, txt)
    return txt

def replace_vn_num(s: str) -> str:
    txt = s
    # longest-first
    for k in sorted(VN_NUM.keys(), key=len, reverse=True):
        txt = re.sub(rf'(?<!\w){re.escape(k)}(?!\w)', str(VN_NUM[k]), txt)
    return txt

def norm(raw: str) -> str:
    """Normalization used for time/date parsing: do NOT remove diacritics globally."""
    t = raw.lower().strip()
    # protect "mốt" so ascii-map won't break it
    t = re.sub(r'\bm[ôo]́?t\b', '__MOT__', t)
    # apply ascii map (handles both no-diacritics and ascii shortcut)
    t = apply_ascii_map(t)
    # replace numbers words
    t = replace_vn_num(t)
    # common punctuation
    t = t.replace(".", ":")
    t = re.sub(r"[,;()]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # restore protected mốt
    t = t.replace('__MOT__', 'mốt')

    return t

# -------------------------
# Time extraction
# -------------------------
def extract_time(t: str) -> Optional[tuple]:
    # 24h style 10:30
    m = re.search(r'\b(\d{1,2}):(\d{1,2})\b', t)
    if m:
        h = int(m.group(1)); mn = int(m.group(2))
        return h, mn

    # 10h30 or "10 h 30" or "10 giờ 30"
    m = re.search(r'\b(\d{1,2})\s*(?:h|giờ)\s*(\d{1,2})\b', t)
    if m:
        h = int(m.group(1)); mn = int(m.group(2))
        # consider time of day words
        if re.search(r'\bsáng\b', t) and h == 12:
            h = 0
        if re.search(r'\btrưa\b', t) and h < 12:
            h = 12
        if re.search(r'\b(chiều|tối|đêm)\b', t) and h < 12:
            h += 12
        return h, mn

    # 10h, 10 h, 10 giờ
    m = re.search(r'\b(\d{1,2})\s*(?:h|giờ)\b', t)
    if m:
        h = int(m.group(1)); mn = 0
        if re.search(r'\bsáng\b', t) and h == 12:
            h = 0
        if re.search(r'\btrưa\b', t) and h < 12:
            h = 12
        if re.search(r'\b(chiều|tối|đêm)\b', t) and h < 12:
            h += 12
        return h, mn

    return None

# -------------------------
# Natural time guesses (tầm chiều / tầm tối)
# -------------------------
def guess_natural_time(t: str) -> Optional[time]:
    if re.search(r'\btầm chiều\b|\btam chieu\b|\btam chieu\b', t):
        return time(15, 0)
    if re.search(r'\btầm tối\b|\btam toi\b', t):
        return time(19, 0)
    if 'giữa trưa' in t or 'giu a trua' in t:
        return time(12, 0)
    return None

# -------------------------
# Date extraction
# -------------------------
WEEKDAY = {
    "thu hai":0, "th2":0, "hai":0,
    "thu ba":1, "th3":1, "ba":1,
    "thu tu":2, "th4":2, "tu":2,
    "thu nam":3, "th5":3, "nam":3,
    "thu sau":4, "th6":4, "sau":4,
    "thu bay":5, "th7":5, "bay":5,
    "chu nhat":6, "cn":6
}

def extract_advanced_relative_date(t: str) -> Optional[date]:
    now = datetime.now(LOCAL_TZ).date()
    wd = now.weekday()
    # tuần sau / tuần tới
    if re.search(r'tuần sau|tuan sau|tuần tới|tuan toi', t):
        return now + timedelta(days=7)
    if re.search(r'cuối tuần|cuoi tuan', t):
        # find next saturday/sunday -> choose sunday as "cuối tuần"
        delta = (6 - wd) if wd <= 6 else 0
        if delta < 0:
            delta += 7
        return now + timedelta(days=delta)
    if re.search(r'đầu tuần|dau tuan', t):
        # next monday
        delta = (0 - wd) if wd <= 0 else (7 - wd)
        if delta == 0:
            delta = 7
        return now + timedelta(days=delta)
    if re.search(r'tháng sau|thang sau', t):
        # next month same day (fallback safe)
        y = now.year; m = now.month + 1
        if m > 12:
            m = 1; y += 1
        d = min(now.day, 28)  # safe
        return date(y, m, d)
    return None

def extract_date(t: str) -> Optional[date]:
    today = datetime.now(LOCAL_TZ).date()
    # advanced patterns first
    adv = extract_advanced_relative_date(t)
    if adv:
        return adv

    if re.search(r'\bhôm nay\b|\bhom nay\b', t):
        return today
    if re.search(r'\bmai\b', t):
        return today + timedelta(days=1)
    if re.search(r'\b(mốt|mot|mót|môt)\b', t):
        return today + timedelta(days=2)
    if re.search(r'(ngày|ngay)\s+(mốt|mot|mót|môt)\b', t):
        return today + timedelta(days=2)
    # "3 ngày nữa"
    m = re.search(r'(\d+)\s*ngày nua|\b(\d+)\s*ngay nua', t)
    if m:
        g = m.group(1) or m.group(2)
        try:
            return today + timedelta(days=int(g))
        except:
            pass
    # weekday phrases
    for k, wd in WEEKDAY.items():
        if k in t:
            delta = (wd - today.weekday() + 7) % 7
            if delta == 0:
                delta = 7
            return today + timedelta(days=delta)
    # explicit dd/mm or dd/mm/yyyy
    m = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', t)
    if m:
        d = int(m.group(1)); mo = int(m.group(2)); y = m.group(3)
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

# -------------------------
# Reminder
# -------------------------
def extract_reminder(t: str) -> int:
    m = re.search(r'nhắc(?: tôi| tui)?\s*(?:trước)?\s*(\d+)\s*(phút|phut|p|ph|giờ|g|h|ngày|ngay)?', t)
    if not m:
        return 15
    n = int(m.group(1))
    unit = (m.group(2) or "phút")
    if 'ngày' in unit or 'ngay' in unit:
        return n * 1440
    if unit in ('giờ','gio','g','h'):
        return n * 60
    return n

def extract_repeat(t: str) -> Optional[str]:
    if re.search(r'mỗi ngày|moi ngay|hàng ngày|hang ngay', t): return "daily"
    if re.search(r'mỗi tuần|moi tuan|hang tuan|hàng tuần|hang tuan', t): return "weekly"
    if re.search(r'mỗi tháng|moi thang|hang thang|hàng tháng|hang thang', t): return "monthly"
    # extended patterns "mỗi 2 ngày" -> every_2_ngay
    m = re.search(r'moi\s+(\d+)\s*(ngay|tuan|thang)', t)
    if m:
        return f"every_{m.group(1)}_{m.group(2)}"
    return None

# -------------------------
# Event name / intent extraction (use remove_diacritics here for robust matching)
# -------------------------
def extract_event_candidate_from_intent(raw: str) -> Optional[str]:
    s = remove_diacritics(raw.lower())
    s = apply_ascii_map(s)
    s = replace_vn_num(s)
    s = re.sub(r'\s+', ' ', s).strip()

    # patterns for intent (no-diacritics)
    patterns = [
        r'(?:muon|can|dinh|hay|giup|tao|tao cho|tao ra)\s+(.*?)(?:,|nhac|luc|o|tai|$)',
        r'(?:toi|tui|tao|minh)\s+(.*?)(?:,|nhac|luc|o|tai|$)'
    ]
    for p in patterns:
        m = re.search(p, s)
        if m:
            cand = m.group(1).strip()
            cand = re.sub(r'\b(toi|tui|tao|minh)\b', '', cand)
            cand = re.sub(r'\b(nhac|truoc|phut|gio|h|ngay)\b.*', '', cand)
            cand = re.sub(r'\bluc\b.*', '', cand)
            cand = re.sub(r'(o|tai)\s+.*', '', cand)
            cand = re.sub(r'\s+', ' ', cand).strip()
            if cand:
                # try to restore accents roughly? keep as is (no-diacritics ok)
                return cand
    return None

def clean_event_name(t: str) -> str:
    # t is normalized (no-diacritics or ascii-mapped). Use intent capture first.
    cand = extract_event_candidate_from_intent(t)
    if cand:
        return cand.strip()
    s = t
    s = re.sub(r'\b(nhắc|nhac|tao|tạo|sự kiện|su kien|hãy|hay|giup|giúp)\b', '', s)
    s = re.sub(r'\d+\s*(phút|phut|p|ph|giờ|gio|g|h)\s*nữa', '', s)
    s = re.sub(r'nhắc.*trước.*', '', s)
    s = re.sub(r'\blúc\b.*', '', s)
    s = re.sub(r'(o|tai)\s+[^,.;]+', '', s)
    s = re.sub(r'(hôm nay|hom nay|mai|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)', '', s)
    s = re.sub(r'\d{1,2}[:h]\d{0,2}', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s if s else "Sự kiện"

# -------------------------
# Location extraction (also use remove_diacritics variant)
# -------------------------
def extract_location(raw: str) -> Optional[str]:
    # try accented first (original text)
    m = re.search(r'\b(?:ở|tại|o|tai)\s+([^,.;]+)', raw, flags=re.IGNORECASE)
    if m:
        loc = m.group(1).strip()
        loc = re.sub(r'(nhé|nhé|giúp|giup|giùm).*', '', loc).strip()
        return loc
    # fallback to no-diacritics form
    s = remove_diacritics(raw.lower())
    m2 = re.search(r'\b(?:o|tai)\s+([^,.;]+)', s)
    if m2:
        return m2.group(1).strip()
    return None

# -------------------------
# Main parser
# -------------------------
def parse_text(text: str) -> Optional[Dict]:
    if not text or not text.strip():
        return None

    raw = text.strip()
    # norm WITHOUT removing diacritics (to avoid breaking dateparser/time recognition)
    t = norm(raw)
    now = datetime.now(LOCAL_TZ)

    # relative minutes/hours
    m_min = re.search(r'(\d+)\s*(phút|phut|p)\s*nữa', t)
    m_hr = re.search(r'(\d+)\s*(giờ|gio|g|h)\s*nữa', t)

    dt_start = None

    if m_min:
        dt_start = now + timedelta(minutes=int(m_min.group(1)))
    elif m_hr:
        dt_start = now + timedelta(hours=int(m_hr.group(1)))

    # remove relative fragment for other extractions
    t_no_relative = re.sub(r'\d+\s*(phút|phut|p|ph|giờ|gio|g|h)\s*nữa', '', t)

    reminder = extract_reminder(t_no_relative)
    repeat = extract_repeat(t)
    location = extract_location(raw)

    # if not relative, try absolute parsing: advanced date -> explicit time -> natural times -> dateparser
    if not dt_start:
        adv_date = extract_advanced_relative_date(t)
        d = adv_date or extract_date(t) or now.date()

        # natural time guesses (tầm chiều...)
        nt = guess_natural_time(t)

        tm = extract_time(t)
        if tm:
            h, mn = tm
            try:
                dt_start = datetime.combine(d, time(h, mn))
            except:
                dt_start = None
        elif nt:
            dt_start = datetime.combine(d, nt)
        else:
            # fallback to dateparser (use raw because it may contain accents)
            try:
                parsed = dateparser.parse(raw, languages=["vi"], default=now)
                if parsed:
                    dt_start = parsed
            except:
                dt_start = None

    if not dt_start:
        return None

    # localize if naive
    if dt_start.tzinfo is None:
        dt_start = LOCAL_TZ.localize(dt_start)
    dt_start = dt_start.replace(second=0, microsecond=0)

    # if time already passed and no explicit 'hôm nay/mai' then move to next day
    if dt_start < now - timedelta(seconds=5):
        dt_start = dt_start + timedelta(days=1)

    # event name extraction: use no-relative normalized form but prefer intent-capture (no-diacritics allowed)
    # pass original raw to intent capture via remove_diacritics inside function
    event_name = clean_event_name(t_no_relative)

    importance = "normal"
    if re.search(r'(quan trọng|uu tiên|uu tien|uu tien)', t):
        importance = "important"
    if re.search(r'(cực quan trọng|khan cap|khan cấp|khan cap|cuc quan trong)', t):
        importance = "critical"

    return {
        "event": event_name,
        "start_time": to_iso(dt_start),
        "end_time": None,
        "location": location,
        "reminder_minutes": int(reminder),
        "importance": importance,
        "repeat": repeat,
        "repeat_count": 0,
        "notified": 0,
        "isStop": 0
    }

# quick self-test if executed directly
if __name__ == "__main__":
    tests = [
        "Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302",
        "tao cho tui mot cuoc hop sang mai luc 6 gio",
        "5 phút nữa tui muốn họp nhóm, nhắc tui trước 3 phút",
        "Tối mai 19:30 gặp Tùng tại quán cà phê, nhắc trước 10 phút.",
        "cuối tuần họp dự án"
    ]
    for s in tests:
        print("INPUT:", s)
        print("OUTPUT:", parse_text(s))
        print("----")
