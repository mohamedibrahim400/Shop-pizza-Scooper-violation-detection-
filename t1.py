# import sqlite3

# conn = sqlite3.connect("violations.db")
# cursor = conn.cursor()

# cursor.execute("""
# CREATE TABLE IF NOT EXISTS violations (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     timestamp TEXT,
#     frame_number INTEGER,
#     image_path TEXT
# )
# """)

# conn.commit()
# conn.close()

# print("✅ Database and table created successfully.")
import sqlite3

conn = sqlite3.connect("violations.db")
cursor = conn.cursor()

# أضف العمود فقط لو مش موجود
try:
    cursor.execute("ALTER TABLE violations ADD COLUMN violation_type TEXT")
    conn.commit()
    print("✅ Added column 'violation_type' to violations table.")
except sqlite3.OperationalError as e:
    print("⚠️ ربما العمود موجود بالفعل أو حصل خطأ:", e)

conn.close()
