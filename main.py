# main.py (UI đẹp — bản sửa hoàn chỉnh)
import streamlit as st
from datetime import datetime, date, time
import pytz
import sqlite3
import calendar

import db, export
import nlp as nlp_module
from reminder import start_reminder_thread, get_streamlit_alerts

# ---------------------------
# INIT
# ---------------------------
db.init_db()
if "reminder_started" not in st.session_state:
    st.session_state.stop_event = start_reminder_thread()
    st.session_state.reminder_started = True

st.set_page_config(page_title="Personal Schedule Assistant", layout="centered")
st.title("🧭 Trợ lý quản lý lịch trình thông minh")

LOCAL_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ---------------------------
# POPUP ALERTS
# ---------------------------
alerts = get_streamlit_alerts()
if alerts:
    st.markdown("### 🔔 Cảnh báo sắp tới")
    for a in alerts:
        st.warning(
            f"**{a['event']}** lúc **{a['time']}** tại **{a['location']}**",
            icon="🚨"
        )

st.markdown("---")

# ---------------------------
# NLP INPUT ONLY
# ---------------------------
st.header("🤖 Thêm sự kiện bằng tiếng Việt (tự nhiên)")
txt = st.text_area(
    "Nhập câu (VD: Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302)\n"
    "Hỗ trợ viết tắt: 'p' -> phút, 'h' hoặc 'g' -> giờ; hỗ trợ không dấu.",
    height=140
)

if st.button("Phân tích câu (NLP)"):
    parsed = nlp_module.parse_text(txt)
    if parsed:
        new_id = db.add_event(
            parsed["event"],
            parsed["start_time"],
            parsed.get("end_time"),
            parsed.get("location"),
            parsed.get("reminder_minutes", 15),
            parsed.get("repeat", None)
        )

        with sqlite3.connect("events.db") as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE events SET
                    importance=?, repeat_count=?, notified=?,
                    isStop=?, pending_auto_mark=0
                WHERE id=?
            """, (
                parsed.get("importance", "normal"),
                parsed.get("repeat_count", 0),
                parsed.get("notified", 0),
                parsed.get("isStop", 0),
                new_id
            ))
            conn.commit()
        st.success("✨ NLP hiểu và thêm sự kiện thành công!")
        st.rerun()
    else:
        st.error("❌ NLP không hiểu câu này, hãy thử lại!")

st.markdown("---")

# ---------------------------
# Calendar view
# ---------------------------
st.header("📆 Lịch (bấm vào ngày để xem sự kiện)")

if "cal_year" not in st.session_state:
    now = datetime.now(LOCAL_TZ)
    st.session_state.cal_year = now.year
    st.session_state.cal_month = now.month
    st.session_state.selected_day = None

# navigation
colm1, colm2, colm3 = st.columns([1,2,1])
with colm1:
    if st.button("◀"):
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
        st.rerun()

with colm2:
    st.markdown(f"### {calendar.month_name[st.session_state.cal_month]} {st.session_state.cal_year}")

with colm3:
    if st.button("▶"):
        if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
        else:
            st.session_state.cal_month += 1
        st.rerun()

events_all = db.list_events()

# build "days that have events"
days_with_events = set()
for e in events_all:
    try:
        dt = datetime.fromisoformat(e["start_time"])
        if dt.tzinfo is None:
            dt = LOCAL_TZ.localize(dt)
        dt = dt.astimezone(LOCAL_TZ)
        if dt.year == st.session_state.cal_year and dt.month == st.session_state.cal_month:
            days_with_events.add(dt.day)
    except:
        pass

# calendar rows
cal = calendar.monthcalendar(st.session_state.cal_year, st.session_state.cal_month)

weekdays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
hdr = st.columns(7)
for i, h in enumerate(weekdays):
    hdr[i].markdown(f"**{h}**")

# render calendar
for week in cal:
    cols = st.columns(7)
    for i, day in enumerate(week):
        if day == 0:
            cols[i].write("")
        else:
            key = f"d_{st.session_state.cal_year}_{st.session_state.cal_month}_{day}"
            label = f"{day} ●" if day in days_with_events else f"{day}"
            if cols[i].button(label, key=key):
                st.session_state.selected_day = date(st.session_state.cal_year, st.session_state.cal_month, day)
                st.rerun()

# ---------------------------
# SELECTED DAY VIEW
# ---------------------------
st.markdown("---")
st.header("📋 Sự kiện theo ngày / Tìm kiếm / Quản lý")

search_q = st.text_input("Tìm kiếm (theo tên / địa điểm)...")

selected = st.session_state.get("selected_day", None)
if selected:
    st.markdown(f"### Sự kiện ngày **{selected.strftime('%d/%m/%Y')}**")
    events_for_day = []

    for e in events_all:
        try:
            dt = datetime.fromisoformat(e["start_time"])
            if dt.tzinfo is None:
                dt = LOCAL_TZ.localize(dt)
            if dt.date() == selected:
                events_for_day.append(e)
        except:
            continue

    if not events_for_day:
        st.info("Không có sự kiện trong ngày này.")
    else:
        for ev in events_for_day:
            st.markdown(
                f"**{ev['event']}**\n"
                f"- ID: `{ev['id']}`\n"
                f"- Lúc: `{ev['start_time']}`\n"
                f"- Địa điểm: `{ev.get('location') or '-'}`\n"
                f"- Nhắc trước: `{ev.get('reminder_minutes')}` phút\n"
                f"- Trạng thái: {'Đã dừng' if ev.get('isStop') else 'Đang hoạt động'}"
            )

            colA, colB, colC = st.columns([1,1,1])

            if colA.button("✏️ Sửa", key=f"edit_day_{ev['id']}"):
                st.session_state.editing = ev["id"]
                st.session_state.edit_payload = ev
                st.rerun()

            if colB.button("❌ Xóa", key=f"del_day_{ev['id']}"):
                db.delete_event(ev["id"])
                st.rerun()

            if colC.button("✔️ Đã nhắc", key=f"mark_day_{ev['id']}"):
                db.update_event_field(ev["id"], "isStop", 1)
                db.mark_notified(ev["id"])
                st.rerun()

# ---------------------------
# SEARCH RESULTS
# ---------------------------
if search_q:
    q = search_q.lower().strip()
    st.markdown(f"### 🔍 Kết quả tìm kiếm: **{q}**")
    lst = []
    for ev in events_all:
        if q in (ev['event'] or "").lower() or q in (ev.get('location') or "").lower():
            lst.append(ev)

    if not lst:
        st.info("Không tìm thấy kết quả.")
    else:
        for ev in lst:
            st.markdown(f"**{ev['event']}** — `{ev['start_time']}` — {ev.get('location') or '-'}")
            c1, c2, c3 = st.columns(3)
            if c1.button("✏️ Sửa", key=f"edit_s_{ev['id']}"):
                st.session_state.editing = ev["id"]
                st.session_state.edit_payload = ev
                st.rerun()
            if c2.button("❌ Xóa", key=f"del_s_{ev['id']}"):
                db.delete_event(ev["id"])
                st.rerun()
            if c3.button("✔️ Đã nhắc", key=f"mark_s_{ev['id']}"):
                db.update_event_field(ev["id"], "isStop", 1)
                db.mark_notified(ev["id"])
                st.rerun()

# ---------------------------
# EDIT EVENT PANEL
# ---------------------------
if st.session_state.get("editing"):
    ev = st.session_state.get("edit_payload")
    st.markdown("---")
    st.markdown(f"### ✏️ Chỉnh sửa sự kiện ID {ev['id']}")

    # parse start_time
    dt = datetime.fromisoformat(ev["start_time"])
    if dt.tzinfo is None:
        dt = LOCAL_TZ.localize(dt)
    dt = dt.astimezone(LOCAL_TZ)

    new_event = st.text_input("Tên sự kiện", ev["event"])
    new_date = st.date_input("Ngày", dt.date())
    new_time = st.time_input("Thời gian", dt.time().replace(second=0, microsecond=0))
    new_location = st.text_input("Địa điểm", ev.get("location") or "")
    new_rem = st.number_input("Nhắc trước (phút)", min_value=0, value=int(ev.get("reminder_minutes") or 15))
    new_imp = st.selectbox("Mức độ quan trọng", ["normal","important","critical"], index=["normal","important","critical"].index(ev.get("importance","normal")))
    new_repeat = st.selectbox("Lặp lại", [None,"daily","weekly","monthly"], index=[None,"daily","weekly","monthly"].index(ev.get("repeat")))

    if st.button("💾 Lưu thay đổi"):
        dt_new = datetime.combine(new_date, new_time)
        dt_new = LOCAL_TZ.localize(dt_new)

        with sqlite3.connect("events.db") as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE events SET
                    event=?, start_time=?, location=?, reminder_minutes=?, importance=?, repeat=?,
                    isStop=0, notified=0, repeat_count=0, pending_auto_mark=0, next_notify=NULL
                WHERE id=?
            """, (
                new_event, dt_new.isoformat(), new_location,
                int(new_rem), new_imp, new_repeat, ev["id"]
            ))
            conn.commit()

        st.success("Đã lưu chỉnh sửa.")
        st.session_state.editing = None
        st.session_state.edit_payload = None
        st.rerun()

    if st.button("Hủy"):
        st.session_state.editing = None
        st.session_state.edit_payload = None
        st.rerun()

st.markdown("---")

# ---------------------------
# EXPORT
# ---------------------------
if st.button("📤 Export .json + .ics"):
    p_json = export.export_json()
    p_ics = export.export_ics()
    st.success(f"Đã export: {p_json}, {p_ics}")
