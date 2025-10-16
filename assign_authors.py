from app import app, db, User, Post

with app.app_context():
    # 建一個預設使用者（若已存在請改用已存在的 id）
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(username='admin')
        u.set_password('changeme')
        db.session.add(u)
        db.session.commit()
        print("Created user admin id=", u.id)
    else:
        print("Found user admin id=", u.id)

    # 把沒有 author_id 的文章指派給 admin
    posts = Post.query.filter((Post.author_id == None) | (Post.author_id == 0)).all()
    for p in posts:
        p.author_id = u.id
    db.session.commit()
    print("Assigned", len(posts), "posts to admin")