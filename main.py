# main.py
import streamlit as st
from datetime import datetime
import db, export
import nlp as nlp_module
from reminder import start_reminder_thread
from dateutil import parser
import pytz

# init DB
db.init_db()

# start reminder thread once
if "reminder_started" not in st.session_state:
    st.session_state.stop_event = start_reminder_thread()
    st.session_state.reminder_started = True

st.set_page_config(page_title="Personal Schedule Assistant", layout="centered")
st.title("Trợ lý quản lý lịch trình (Personal Schedule Assistant)")

st.header("Thêm sự kiện (thủ công)")
with st.form("manual_form"):
    event_name = st.text_input("Tên sự kiện", "")
    date_input = st.date_input("Ngày", value=datetime.now().date())
    time_input = st.time_input("Giờ bắt đầu", value=datetime.now().time().replace(second=0, microsecond=0))
    location = st.text_input("Địa điểm (tuỳ chọn)", "")
    reminder_minutes = st.number_input("Nhắc trước (phút)", min_value=0, value=15)

    submitted = st.form_submit_button("Thêm sự kiện")

    if submitted:
        local_tz = pytz.timezone("Asia/Ho_Chi_Minh")

        # ✅ combine date + time chuẩn local
        dt_local = datetime.combine(date_input, time_input)
        dt_local = local_tz.localize(dt_local)  # thêm timezone local
        iso = dt_local.isoformat()

        db.add_event(event_name, iso, None, location, int(reminder_minutes))
        st.success(f"✅ Đã thêm sự kiện '{event_name}' vào lúc {dt_local.strftime('%H:%M %d/%m/%Y')}")


st.markdown("---")
st.header("Thêm sự kiện bằng tiếng Việt (tự nhiên)")
txt = st.text_area("Nhập câu (VD: Nhắc tôi họp nhóm lúc 10 giờ sáng mai ở phòng 302)", height=120)
if st.button("Phân tích (gọi NLP)"):
    parsed = nlp_module.parse_text(txt)
    if parsed:
        db.add_event(parsed["event"], parsed["start_time"], parsed.get("end_time"), parsed.get("location"), parsed.get("reminder_minutes", 15))
        st.success("Phân tích thành công, đã lưu.")
    else:
        st.error("Không phân tích được, bạn có thể nhập thủ công hoặc sửa câu.")

st.markdown("---")
st.header("Danh sách sự kiện")
events = db.list_events()
if not events:
    st.info("Chưa có sự kiện nào.")
for ev in events:
    st.write(f"ID: {ev['id']}  |  {ev['event']}  |  {ev['start_time']}  |  Địa điểm: {ev.get('location') or '-'}  | Nhắc trước: {ev.get('reminder_minutes')}")
    cols = st.columns(3)
    if cols[0].button("Xoá", key=f"del_{ev['id']}"):
        db.delete_event(ev["id"])
        try:
            # dùng rerun phù hợp phiên bản
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()
        except Exception as e:
            st.warning(f"Đã xoá (reload trang để cập nhật). Lỗi rerun: {e}")
    if cols[1].button("Xuất .ics", key=f"ics_{ev['id']}"):
        export.export_ics(path=f"event_{ev['id']}.ics")
        st.success("Đã xuất .ics")
    if cols[2].button("Đánh dấu đã nhắc", key=f"mark_{ev['id']}"):
        db.mark_notified(ev["id"])
        st.success("Đã đánh dấu")

st.markdown("---")
if st.button("Export toàn bộ (.json & .ics)"):
    p_json = export.export_json()
    p_ics = export.export_ics()
    st.success(f"Export xong: {p_json}, {p_ics}")
