import sqlite3

conn = sqlite3.connect("readygrad.db")
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", cur.fetchall())

cur.execute("SELECT * FROM jobs;")
rows = cur.fetchall()
print(f"\n{len(rows)} jobs found:\n")
for row in rows:
    print(row)

conn.close()