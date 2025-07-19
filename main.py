from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from ultralytics import YOLO
import sqlite3
import os
import cv2
from datetime import datetime

app = FastAPI()

# تحميل الموديل
model = YOLO("models/best.pt")

# إنشاء مجلدات
os.makedirs("violations", exist_ok=True)
os.makedirs("snapshots", exist_ok=True)

# إعداد قاعدة البيانات
DB_PATH = "violations.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    image_path TEXT,
    violation_type TEXT
)
''')
conn.commit()

# منطقة المراقبة ROI
ROI = (150, 250, 550, 750)

# 🔹 دوال مساعدة

def is_inside_roi(box, roi):
    x1, y1, x2, y2 = map(int, box)
    rx1, ry1, rx2, ry2 = roi
    return (x1 >= rx1 and y1 >= ry1 and x2 <= rx2 and y2 <= ry2)

def boxes_close(box1, box2, threshold=100):
    x1, y1, x2, y2 = map(int, box1)
    cx1, cy1 = (x1 + x2) // 2, (y1 + y2) // 2
    x1, y1, x2, y2 = map(int, box2)
    cx2, cy2 = (x1 + x2) // 2, (y1 + y2) // 2
    dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
    return dist < threshold

def record_violation(frame):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        snapshot_path = f"snapshots/violation_{timestamp}.jpg"
        cv2.imwrite(snapshot_path, frame)
        cursor.execute(
            "INSERT INTO violations (timestamp, image_path, violation_type) VALUES (?, ?, ?)",
            (timestamp, snapshot_path, "hand_in_roi_without_scooper")
        )
        conn.commit()
        print(f"[⚠️] Violation recorded: {snapshot_path}")
    except Exception as e:
        print(f"[Error] Failed to record violation: {e}")

def review_recent_violations():
    cursor.execute("SELECT id, image_path FROM violations ORDER BY id DESC LIMIT 5")
    for row in cursor.fetchall():
        vid, img_path = row
        if not os.path.exists(img_path):
            continue
        frame = cv2.imread(img_path)
        if frame is None or frame.size == 0:
            continue
        results = model(frame)[0]
        hands = []
        scoopers = []
        for box in results.boxes:
            cls = int(box.cls[0])
            label = model.names[cls].lower()
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            if label == "hand":
                hands.append([x1, y1, x2, y2])
            elif label == "scooper":
                scoopers.append([x1, y1, x2, y2])
        for hand in hands:
            for scooper in scoopers:
                if boxes_close(hand, scooper):
                    cursor.execute("DELETE FROM violations WHERE id = ?", (vid,))
                    conn.commit()
                    os.remove(img_path)
                    print(f"[🟢] Violation removed after review: {img_path}")
                    break

# 🔹 الفيديو
def generate_video():
    cap = cv2.VideoCapture("videos/Sah w b3dha ghalt (2).mp4")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)[0]
        hands, scoopers = [], []

        for box in results.boxes:
            cls = int(box.cls[0])
            label = model.names[cls].lower()
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            color = (0, 255, 0) if label == "scooper" else (0, 0, 255) if label == "hand" else (255, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            if label == "hand":
                hands.append([x1, y1, x2, y2])
            elif label == "scooper":
                scoopers.append([x1, y1, x2, y2])

        # كشف المخالفة
        for hand in hands:
            if is_inside_roi(hand, ROI):
                holding = any(boxes_close(hand, scooper) for scooper in scoopers)
                if not holding:
                    record_violation(frame)
                    break

        # مراجعة المخالفات السابقة
        review_recent_violations()

        # رسم ROI
        cv2.rectangle(frame, (ROI[0], ROI[1]), (ROI[2], ROI[3]), (255, 0, 0), 2)

        # بث الإطار
        _, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

    cap.release()



@app.get("/violations/count")
def get_violation_count():
    cursor.execute("SELECT COUNT(*) FROM violations")
    count = cursor.fetchone()[0]
    return {"violation_count": count}

@app.get("/video/stream")
def video_feed():
    return StreamingResponse(generate_video(), media_type="multipart/x-mixed-replace; boundary=frame")
