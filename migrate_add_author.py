import os
import sqlite3
from app import app, db, User, Post

with app.app_context():
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    print("DB url:", db_uri)

    if not db_uri or not db_uri.startswith("sqlite:///"):
        print("Not an sqlite DB or DB URI missing. Aborting.")
        raise SystemExit(1)

    raw_path = db_uri.replace("sqlite:///", "")
    # 解析成專案內的絕對路徑（若原本是相對路徑）
    if not os.path.isabs(raw_path):
        base = os.path.abspath(os.path.dirname(__file__))  # 專案檔案所在資料夾
        db_path = os.path.abspath(os.path.join(base, raw_path))
    else:
        db_path = os.path.abspath(raw_path)

    print("Resolved DB file path:", db_path)
    print("Current working dir:", os.getcwd())

    if not os.path.exists(db_path):
        print("DB file not found at resolved path:", db_path)
        print("如果你要建立新 DB，請先執行： python -m flask init-db")
        raise SystemExit(1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='post'")
    if not cur.fetchone():
        print("Table 'post' 不存在。請先建立 schema（python -m flask init-db）。")
        conn.close()
        raise SystemExit(1)

    cur.execute("PRAGMA table_info('post')")
    cols = [r[1] for r in cur.fetchall()]
    print("post columns:", cols)

    if 'author_id' not in cols:
        print("Adding author_id column to post...")
        cur.execute("ALTER TABLE post ADD COLUMN author_id INTEGER;")
        conn.commit()
        print("author_id added.")
    else:
        print("author_id already present.")
    conn.close()

    # 建 admin（若不存在）
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(username='admin')
        u.set_password('changeme')
        db.session.add(u)
        db.session.commit()
        print("Created user admin id=", u.id)
    else:
        print("Found user admin id=", u.id)

    posts_to_assign = Post.query.filter((Post.author_id == None) | (Post.author_id == 0)).all()
    for p in posts_to_assign:
        p.author_id = u.id
    db.session.commit()
    print("Assigned", len(posts_to_assign), "posts to admin")