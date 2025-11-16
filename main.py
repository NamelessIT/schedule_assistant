# main.py
import streamlit as st
from datetime import datetime
import pytz
import sqlite3

import db, export
import nlp as nlp_module
from reminder import start_reminder_thread, get_streamlit_alerts

# =============================
# INIT DB + REMINDER THREAD
# =============================
db.init_db()

if "reminder_started" not in st.session_state:
    st.session_state.stop_event = start_reminder_thread()
    st.session_state.reminder_started = True

st.set_page_config(page_title="Personal Schedule Assistant", layout="centered")
st.title("🧭 Trợ lý quản lý lịch trình thông minh")

# =============================
# STREAMLIT POPUP CẢNH BÁO
# =============================
alerts = get_streamlit_alerts()
if alerts:
    st.markdown("### 🔔 Cảnh báo sắp tới")
    for a in alerts:
        st.warning(
            f"**{a['event']}** lúc **{a['time']}** tại **{a['location']}**",
            icon="🚨"
        )

# =============================
# THÊM SỰ KIỆN THỦ CÔNG
# =============================
st.header("➕ Thêm sự kiện (thủ công)")

with st.form("manual_form"):
    event_name = st.text_input("Tên sự kiện", "")
    date_input = st.date_input("Ngày", value=datetime.now().date())
    time_input = st.time_input(
        "Giờ bắt đầu",
        value=datetime.now().time().replace(second=0, microsecond=0)
    )
    location = st.text_input("Địa điểm", "")
    reminder_minutes = st.number_input("Nhắc trước (phút)", min_value=0, value=15)

    importance = st.selectbox(
        "Mức độ quan trọng",
        ["Bình thường", "Quan trọng", "Cực quan trọng"],
        index=0
    )

    repeat = st.selectbox(
        "Lặp lại",
        ["Không lặp", "Hàng ngày", "Hàng tuần", "Hàng tháng"],
        index=0
    )

    importance_map = {
        "Bình thường": "normal",
        "Quan trọng": "important",
        "Cực quan trọng": "critical"
    }
    repeat_map = {
        "Không lặp": None,
        "Hàng ngày": "daily",
        "Hàng tuần": "weekly",
        "Hàng tháng": "monthly"
    }

    importance_value = importance_map[importance]
    repeat_value = repeat_map[repeat]

    submitted = st.form_submit_button("Thêm sự kiện")

    if submitted:
        local_tz = pytz.timezone("Asia/Ho_Chi_Minh")
        dt_local = datetime.combine(date_input, time_input)
        dt_local = local_tz.localize(dt_local)
        iso = dt_local.isoformat()

        # add event
        new_id = db.add_event(
            event_name,
            iso,
            None,
            location,
            int(reminder_minutes),
            repeat_value
        )

        # update importance
        with sqlite3.connect("events.db") as conn:
            cur = conn.cursor()
            cur.execute("UPDATE events SET importance=? WHERE id=?", (importance_value, new_id))
            conn.commit()

        st.success(f"🎉 Đã thêm sự kiện **{event_name}**!")

st.markdown("---")

# =============================
# NLP INPUT
# =============================
st.header("🤖 Thêm sự kiện bằng tiếng Việt tự nhiên")

txt = st.text_area(
    "Nhập câu (VD: Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302)",
    height=130
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

        # add extra fields
        with sqlite3.connect("events.db") as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE events SET
                    importance=?,
                    repeat_count=?,
                    notified=?,
                    isStop=?,
                    pending_auto_mark=0
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

    else:
        st.error("❌ NLP không hiểu câu này, hãy thử lại!")

st.markdown("---")

# =============================
# EVENT LIST
# =============================
st.header("📅 Danh sách sự kiện")

events = db.list_events()

if not events:
    st.info("Chưa có sự kiện nào!")

importance_icon = {
    "normal": "⚪",
    "important": "🟡",
    "critical": "🔴"
}

repeat_text = {
    None: "Không lặp",
    "daily": "Hàng ngày",
    "weekly": "Hàng tuần",
    "monthly": "Hàng tháng"
}

for ev in events:
    icon = importance_icon.get(ev.get("importance", "normal"), "⚪")
    status = "Đã dừng" if ev.get("isStop") else "Đang hoạt động"
    repeat_label = repeat_text.get(ev.get("repeat"))

    st.markdown(
        f"{icon} **{ev['event']}**\n"
        f"- ID: `{ev['id']}`\n"
        f"- Thời gian: `{ev['start_time']}`\n"
        f"- Địa điểm: `{ev.get('location') or '-'}`\n"
        f"- Nhắc trước: `{ev.get('reminder_minutes')}` phút\n"
        f"- Lặp lại: **{repeat_label}**\n"
        f"- Trạng thái: **{status}**\n"
    )

    cols = st.columns(4)

    if cols[0].button("❌ Xoá", key=f"del_{ev['id']}"):
        db.delete_event(ev["id"])
        st.rerun()

    if cols[1].button("⏹ Dừng", key=f"stop_{ev['id']}"):
        db.update_event_field(ev["id"], "isStop", 1)
        st.rerun()

    if cols[2].button("▶️ Kích hoạt", key=f"resume_{ev['id']}"):
        db.update_event_field(ev["id"], "isStop", 0)
        db.update_event_field(ev["id"], "repeat_count", 0)
        db.update_event_field(ev["id"], "notified", 0)
        db.update_event_field(ev["id"], "pending_auto_mark", 0)
        st.rerun()

    if cols[3].button("✔️ Đã nhắc", key=f"mark_{ev['id']}"):
        db.update_event_field(ev["id"], "isStop", 1)
        db.mark_notified(ev["id"])
        st.success("Đã đánh dấu")
        st.rerun()

st.markdown("---")

# =============================
# EXPORT
# =============================
st.header("📤 Xuất dữ liệu")

if st.button("Export .json + .ics"):
    p_json = export.export_json()
    p_ics = export.export_ics()
    st.success(f"Đã export: {p_json}, {p_ics}")
