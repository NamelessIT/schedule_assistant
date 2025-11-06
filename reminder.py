# reminder.py (đã sửa hoàn toàn)
import threading
import time
from datetime import datetime, timedelta
import pytz
from plyer import notification
from db import list_events, mark_notified
from dateutil import parser

CHECK_INTERVAL = 30  # giây, bạn có thể giảm xuống 10 để test nhanh

def send_notification(title: str, message: str):
    """Hiển thị thông báo hệ thống."""
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=10
        )
        print(f"[INFO] Notification sent: {title} - {message}")
    except Exception as e:
        print("[ERROR] Notification error:", e)

def reminder_loop(stop_event: threading.Event):
    local_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    while not stop_event.is_set():
        now_local = datetime.now(local_tz)
        events = list_events()
        print(f"[DEBUG] Kiểm tra {len(events)} sự kiện lúc {now_local.strftime('%H:%M:%S')}")

        for ev in events:
            if ev.get("notified", 0) == 1:
                continue

            try:
                start = parser.isoparse(ev["start_time"])
            except Exception as e:
                print("[WARN] Không parse được start_time:", ev["start_time"], e)
                continue

            # Nếu datetime không có timezone → gán Asia/Ho_Chi_Minh
            if start.tzinfo is None:
                start = local_tz.localize(start)

            reminder_min = int(ev.get("reminder_minutes") or 0)
            remind_time = start - timedelta(minutes=reminder_min)

            # So sánh theo cùng timezone
            if remind_time <= now_local:
                title = f"⏰ Nhắc: {ev['event']}"
                loc = ev.get("location") or ""
                msg = f"Bắt đầu lúc {start.strftime('%H:%M %d/%m/%Y')} tại {loc}"
                send_notification(title, msg)
                mark_notified(ev["id"])
                print(f"[REMINDER] {title} - {msg}")

        stop_event.wait(CHECK_INTERVAL)

def start_reminder_thread():
    stop_event = threading.Event()
    t = threading.Thread(target=reminder_loop, args=(stop_event,), daemon=True)
    t.start()
    return stop_event
