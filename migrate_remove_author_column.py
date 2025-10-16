import os
import shutil
import sqlite3
from datetime import datetime
from app import app, db, User

with app.app_context():
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri or not db_uri.startswith("sqlite:///"):
        print("非 sqlite DB 或 DB URI 缺失，終止。")
        raise SystemExit(1)

    raw_path = db_uri.replace("sqlite:///", "")
    if not os.path.isabs(raw_path):
        base = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.abspath(os.path.join(base, raw_path))
    else:
        db_path = os.path.abspath(raw_path)

    if not os.path.exists(db_path):
        print("找不到 DB 檔案:", db_path)
        raise SystemExit(1)

    # 備份
    bak_name = f"{db_path}.bak_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(db_path, bak_name)
    print("已備份 DB 到:", bak_name)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 取得 post 欄位
    cur.execute("PRAGMA table_info('post')")
    cols_info = cur.fetchall()
    cols = [r[1] for r in cols_info]
    print("post columns:", cols)

    if 'author' not in cols:
        print("表格已無 author 欄位，無需移除。")
        conn.close()
        raise SystemExit(0)

    # 建 admin（若不存在）
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(username='admin')
        u.set_password('changeme')
        db.session.add(u)
        db.session.commit()
        print("建立 admin 帳號 id=", u.id)
    else:
        print("找到 admin id=", u.id)
    admin_id = u.id

    # 關閉 foreign keys
    cur.execute("PRAGMA foreign_keys=OFF;")
    conn.commit()

    # 建新的 post table（不含 author 欄位）
    cur.execute("""
    CREATE TABLE post_new (
        id INTEGER PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        author_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY(author_id) REFERENCES user(id)
    );
    """)
    conn.commit()
    print("已建立 post_new")

    # 將舊資料搬入 post_new
    # 邏輯：若 author_id 存在且不為 NULL -> 用它
    # 否則若 author (文字) 對應到 existing user.username -> 用該 user.id
    # 否則把該筆指派給 admin
    cur.execute("SELECT id, title, author_id, author, content, created_at, updated_at FROM post")
    rows = cur.fetchall()
    inserted = 0
    for r in rows:
        old_id, title, a_id, a_text, content, created_at, updated_at = r
        target_author_id = None
        if a_id not in (None, 0):
            target_author_id = a_id
        elif a_text:
            # 嘗試在 user table 找 username 相符者
            cur_user = conn.execute("SELECT id FROM user WHERE username = ?", (a_text,)).fetchone()
            if cur_user:
                target_author_id = cur_user[0]
            else:
                target_author_id = admin_id
        else:
            target_author_id = admin_id

        cur.execute(
            "INSERT INTO post_new (id, title, author_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (old_id, title, target_author_id, content, created_at, updated_at)
        )
        inserted += 1
    conn.commit()
    print(f"已搬入 {inserted} 筆資料到 post_new")

    # 刪除舊表並改名
    cur.execute("DROP TABLE post;")
    conn.commit()
    cur.execute("ALTER TABLE post_new RENAME TO post;")
    conn.commit()

    # 開啟 foreign keys
    cur.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.close()

    print("完成：已移除 author 欄位並保留資料。請重新啟動應用測試。")