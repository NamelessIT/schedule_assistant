# 🧭 Personal Schedule Assistant

**Ứng dụng quản lý lịch trình thông minh – nhập tiếng Việt tự nhiên, nhắc nhở đa cấp độ, lặp theo ngày/tuần/tháng, auto-stop & popup cảnh báo.**

---

## 🚀 Giới thiệu

Dự án giúp người dùng **tạo – quản lý – nhắc lịch** bằng 2 cách:

### **1. Nhập thủ công**

* Tên sự kiện
* Ngày giờ
* Nhắc trước X phút
* Quan trọng / Cực quan trọng
* Lặp lại: hàng ngày / hàng tuần / hàng tháng

### **2. Nhập bằng tiếng Việt tự nhiên (NLP)**
Hệ thống NLP có thể:

* Hiểu thời gian bằng chữ ("mười một giờ")
* Hiểu thời gian tương đối ("5 phút nữa")
* Hiểu nhắc trước ("nhắc trước 3 phút")
* Hiểu địa điểm
* Hiểu mức độ quan trọng
* Hiểu lặp lại
* Tự làm sạch tên sự kiện

---

## 🔔 Tính năng nổi bật

### ✔ Nhắc nhiều lần nếu là sự kiện **Quan trọng / Cực quan trọng**

| Mức độ         | Số lần nhắc |
| -------------- | ----------- |
| Bình thường    | 1           |
| Quan trọng     | 2           |
| Cực quan trọng | 3           |

---

### ✔ Popup nhắc việc ngay trong hệ thống + trên máy (plyer)

### ✔ Hỗ trợ các dạng lặp:

* **Không lặp**
* **Hàng ngày**
* **Hàng tuần**
* **Hàng tháng**

Mỗi lần lặp sẽ tự động tính lại:

* `start_time`
* `next_notify`
* `repeat_count`
* `pending_auto_mark`

---

### ✔ Auto-Stop thông minh

Nếu một sự kiện **không lặp**, sau khi nhắc đủ số lần → tự chuyển sang:

```
isStop = 1
notified = 1
next_notify = NULL
pending_auto_mark = 0
```

Hiển thị trên giao diện là **Đã dừng**.

---

### ✔ Auto-mark sau 5 phút nếu người dùng không xác nhận

(giống Google Calendar)

---

### ✔ Giao diện Streamlit trực quan

* Danh sách sự kiện
* Các nút: Xóa / Dừng / Kích hoạt / Đã nhắc
* Hiển thị cảnh báo

---

## 📂 Cấu trúc dự án

```
schedule_assistant/
│
├── main.py                 # Streamlit UI
├── nlp.py                  # NLP tiếng Việt tự nhiên
├── reminder.py             # Thread nhắc lịch thông minh
├── db.py                   # SQLite helper
├── export.py               # Xuất JSON + ICS
├── events.db               # Database
├── README.md
└── requirements.txt
```

---

## 🛠 Cài đặt môi trường

### 1️⃣ Tạo môi trường ảo

```sh
python -m venv .venv
```

### 2️⃣ Kích hoạt

**Windows**

```sh
.venv\Scripts\activate
```

**Mac/Linux**

```sh
source .venv/bin/activate
```

### 3️⃣ Cài dependencies

```sh
pip install -r requirements.txt
```

---

## ▶️ Chạy ứng dụng

```sh
streamlit run main.py
```

---

## 🤖 Cách dùng NLP

Nhập câu tiếng Việt tự nhiên:

```
nhắc tui 5 phút nữa đi học, nhắc trước 1 phút
tạo cho tui sự kiện test lúc 20h ở công viên
gặp tùng tối mai lúc 19:30, nhắc trước 10 phút
```

Ứng dụng sẽ tự động:

* Nhận dạng event_name
* Thời gian
* Thời gian lặp
* Nhắc trước
* Quan trọng / Cực quan trọng
* Địa điểm

---

## 📤 Xuất dữ liệu

Ứng dụng hỗ trợ:

* Xuất toàn bộ lịch dạng **JSON**
* Xuất **ICS** tương thích Google Calendar, Outlook

---
