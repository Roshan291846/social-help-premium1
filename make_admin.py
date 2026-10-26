import sqlite3, sys, os
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "social_help.db")
if len(sys.argv) != 2:
    print("Usage: python make_admin.py your-email@example.com")
    raise SystemExit(1)
email = sys.argv[1].strip().lower()
if not os.path.exists(db_path):
    print("Database not found. Run app.py and register an account first.")
    raise SystemExit(1)
conn = sqlite3.connect(db_path)
cur = conn.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
conn.commit()
if cur.rowcount:
    print("Admin enabled for", email)
else:
    print("No user found with that email. Register first.")
conn.close()
