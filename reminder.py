# reminder.py (v6.1) - supports daily/weekly/monthly repeat and auto-stop
import threading
from datetime import datetime, timedelta
import pytz
from plyer import notification
from db import list_events, mark_notified, update_event_field, DB_PATH
from dateutil import parser
from dateutil.relativedelta import relativedelta
import sqlite3

CHECK_INTERVAL = 5        # seconds poll
REPEAT_DELAY = 60         # seconds between repeated notifications
AUTO_MARK_DELAY = 5 * 60  # seconds to auto-mark if user does not dismiss (5 minutes)

LOCAL_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
global_streamlit_alerts = []


def send_notification(title: str, message: str):
    try:
        notification.notify(title=title, message=message, timeout=10)
        print(f"[INFO] Notification sent: {title}")
    except Exception as e:
        print("[ERROR] Notification error:", e)


def add_streamlit_alert(event):
    global global_streamlit_alerts
    alert = {
        "event": event["event"],
        "time": event["start_time"],
        "location": event.get("location"),
        "importance": event.get("importance", "normal")
    }
    global_streamlit_alerts.append(alert)


def get_streamlit_alerts():
    global global_streamlit_alerts
    return global_streamlit_alerts[-8:]


def _parse_iso(s):
    try:
        return parser.isoparse(s)
    except Exception:
        return None


def _floor_to_min(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def _schedule_next_occurrence(cur, ev, start_dt, reminder_min):
    rep = ev.get("repeat")
    if not rep:
        return False

    if rep == "daily":
        new_start = start_dt + timedelta(days=1)
    elif rep == "weekly":
        new_start = start_dt + timedelta(days=7)
    elif rep == "monthly":
        new_start = start_dt + relativedelta(months=1)
    else:
        return False

    next_notify_dt = _floor_to_min(new_start - timedelta(minutes=int(reminder_min or 0)))

    cur.execute("""
        UPDATE events
        SET start_time=?, repeat_count=0, notified=0, next_notify=?, pending_auto_mark=0
        WHERE id=?
    """, (new_start.isoformat(), next_notify_dt.isoformat(), ev["id"]))

    return True


def reminder_loop(stop_event: threading.Event):
    while not stop_event.is_set():

        now_local = datetime.now(LOCAL_TZ)
        events = list_events()
        print(f"[DEBUG] Kiểm tra {len(events)} sự kiện lúc {now_local.strftime('%H:%M:%S')}")

        next_wakeup_seconds = CHECK_INTERVAL

        for ev in events:
            try:
                if ev.get("isStop", 0) == 1:
                    continue

                start_raw = ev.get("start_time")
                start_dt = _parse_iso(start_raw)
                if not start_dt:
                    continue
                if start_dt.tzinfo is None:
                    start_dt = LOCAL_TZ.localize(start_dt)

                start_dt = _floor_to_min(start_dt)

                reminder_min = int(ev.get("reminder_minutes") or 0)
                base_remind = _floor_to_min(start_dt - timedelta(minutes=reminder_min))

                next_notify_raw = ev.get("next_notify")
                if next_notify_raw:
                    next_notify = _parse_iso(next_notify_raw)
                    if next_notify and next_notify.tzinfo is None:
                        next_notify = LOCAL_TZ.localize(next_notify)
                else:
                    next_notify = base_remind

                if next_notify:
                    next_notify = _floor_to_min(next_notify)

                importance = ev.get("importance", "normal")
                max_repeat = {"normal": 1, "important": 2, "critical": 3}.get(importance, 1)
                repeat_count = int(ev.get("repeat_count") or 0)
                pending_auto = int(ev.get("pending_auto_mark") or 0)

                secs_until = (next_notify - now_local).total_seconds() if next_notify else float('inf')

                # -----------------------------
                # AUTO-MARK LOGIC (after grace period)
                # -----------------------------
                if pending_auto == 1 and secs_until <= 0:
                    print(f"[INFO] Auto-marking event id={ev['id']}")

                    update_event_field(ev["id"], "isStop", 1)
                    mark_notified(ev["id"])

                    update_event_field(ev["id"], "next_notify", None)
                    update_event_field(ev["id"], "pending_auto_mark", 0)

                    continue

                # -----------------------------
                # MAIN NOTIFICATION LOGIC
                # -----------------------------
                if secs_until <= 0 and repeat_count < max_repeat:

                    send_notification(
                        f"🔔 {ev['event']} ({importance})",
                        f"Bắt đầu lúc {start_dt.strftime('%H:%M %d/%m/%Y')} tại {ev.get('location') or '-'}"
                    )
                    add_streamlit_alert(ev)

                    with sqlite3.connect(DB_PATH) as conn:
                        cur = conn.cursor()

                        cur.execute(
                            "UPDATE events SET repeat_count = repeat_count + 1 WHERE id=?",
                            (ev["id"],)
                        )
                        conn.commit()

                        cur.execute("SELECT repeat_count FROM events WHERE id=?", (ev["id"],))
                        updated_rc = cur.fetchone()[0]

                        # still can notify more times
                        if updated_rc < max_repeat:
                            next_dt = _floor_to_min(now_local + timedelta(seconds=REPEAT_DELAY))
                            cur.execute("UPDATE events SET next_notify=? WHERE id=?", (next_dt.isoformat(), ev["id"]))
                            conn.commit()

                        else:
                            # last repeat reached
                            if ev.get("repeat"):
                                scheduled = _schedule_next_occurrence(cur, ev, start_dt, reminder_min)
                                if scheduled:
                                    conn.commit()
                                else:
                                    cur.execute("""
                                        UPDATE events
                                        SET notified=1, isStop=1, next_notify=NULL, pending_auto_mark=0
                                        WHERE id=?
                                    """, (ev["id"],))
                                    conn.commit()
                            else:
                                # NON-REPEATING: AUTO-STOP immediately (not waiting 5 min)
                                cur.execute("""
                                    UPDATE events
                                    SET notified=1, isStop=1, next_notify=NULL, pending_auto_mark=0
                                    WHERE id=?
                                """, (ev["id"],))
                                conn.commit()

                else:
                    if secs_until > 0:
                        candidate = max(0.5, min(secs_until, CHECK_INTERVAL))
                        next_wakeup_seconds = min(next_wakeup_seconds, candidate)

            except Exception as e:
                print("[ERROR] reminder loop:", e)
                continue

        stop_event.wait(max(0.5, next_wakeup_seconds))


def start_reminder_thread():
    stop_event = threading.Event()
    t = threading.Thread(target=reminder_loop, args=(stop_event,), daemon=True)
    t.start()
    print("[INFO] Reminder thread started.")
    return stop_event
