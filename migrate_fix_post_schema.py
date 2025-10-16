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
    cols = [r[1] for r in cur.fetchall()]
    print("post columns:", cols)

    if 'author' in cols and 'author_id' not in cols:
        print("偵測到舊 schema (author 存在, author_id 不存在)。準備遷移...")

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

        # 關閉 foreign keys，開始 transaction
        cur.execute("PRAGMA foreign_keys=OFF;")
        conn.commit()

        # 建立新 table post_new、複製資料（把 author 轉換為 author_id=admin_id）
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

        # 若舊 table 有 created_at/updated_at/其他欄位名稱不同，適度調整 SELECT 列
        cur.execute("""
        INSERT INTO post_new (id, title, author_id, content, created_at, updated_at)
        SELECT id, title, ?, content,
               CASE WHEN created_at IS NULL THEN NULL ELSE created_at END,
               CASE WHEN updated_at IS NULL THEN NULL ELSE updated_at END
        FROM post;
        """, (admin_id,))
        conn.commit()

        # 刪除舊 table、改名
        cur.execute("DROP TABLE post;")
        conn.commit()
        cur.execute("ALTER TABLE post_new RENAME TO post;")
        conn.commit()

        # 開啟 foreign keys
        cur.execute("PRAGMA foreign_keys=ON;")
        conn.commit()

        print("遷移完成。舊的 author 欄位已移除，所有舊文章 author_id 設為 admin。")
    else:
        print("不需要遷移：author_id 已存在或不存在 author 欄位。")

    conn.close()