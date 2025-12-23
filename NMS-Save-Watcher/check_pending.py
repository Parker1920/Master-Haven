import sqlite3

conn = sqlite3.connect(r"c:\Master-Haven\Haven-UI\data\haven_ui.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Looking for companion_app submissions ===")
cur.execute("SELECT id, submitted_by, submission_date, status, system_name, source, api_key_name FROM pending_systems WHERE source = 'companion_app' ORDER BY id DESC LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(dict(r))
else:
    print("No companion_app submissions found")

print("\n=== Looking for PENDING status submissions ===")
cur.execute("SELECT id, submitted_by, submission_date, status, system_name, source, api_key_name FROM pending_systems WHERE status = 'pending' ORDER BY id DESC LIMIT 10")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(dict(r))
else:
    print("No pending submissions found - all have been reviewed")

print("\n=== Most recent 3 submissions (any status) ===")
cur.execute("SELECT id, submitted_by, submission_date, status, system_name, source, api_key_name FROM pending_systems ORDER BY id DESC LIMIT 3")
for r in cur.fetchall():
    print(dict(r))

conn.close()
