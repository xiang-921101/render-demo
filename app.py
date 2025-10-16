from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

basedir = os.path.abspath(os.path.dirname(__file__))

# changed code: 建立 app 物件並設定 instance 路徑與 DB URI（必須先有 app）
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_change")

# 確保 instance 資料夾存在，並把 DB 放在 instance/blog.db
instance_dir = os.path.join(basedir, "instance")
os.makedirs(instance_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_dir, 'blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author.username if self.author else None,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# CLI helper
@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Initialized the database.")

# 公開頁面
@app.route("/")
def index():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("index.html", posts=posts)

@app.route("/posts/new")
@login_required
def new_post_form():
    return render_template("new_post.html")

@app.route("/posts", methods=["POST"])
@login_required
def create_post_from_form():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if not title or not content:
        return render_template("new_post.html", error="請填寫所有欄位", title=title, content=content)
    post = Post(title=title, author_id=current_user.id, content=content)
    db.session.add(post)
    db.session.commit()
    return redirect(url_for("view_post", post_id=post.id))

@app.route("/posts/<int:post_id>")
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", post=post)

@app.route("/posts/<int:post_id>/edit")
@login_required
def edit_post_form(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        abort(403)
    return render_template("edit_post.html", post=post)

@app.route("/posts/<int:post_id>/edit", methods=["POST"])
@login_required
def update_post_from_form(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        abort(403)
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    if not title or not content:
        return render_template("edit_post.html", post=post, error="請填寫所有欄位")
    post.title = title
    post.content = content
    db.session.commit()
    return redirect(url_for("view_post", post_id=post.id))

@app.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post_from_form(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for("index"))

# Auth: register / login / logout
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="請輸入帳號與密碼", username=username)
        if User.query.filter_by(username=username).first():
            return render_template("register.html", error="使用者已存在", username=username)
        u = User(username=username)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = User.query.filter_by(username=username).first()
        if not u or not u.check_password(password):
            return render_template("login.html", error="帳號或密碼錯誤", username=username)
        login_user(u)
        return redirect(request.args.get('next') or url_for("index"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# RESTful API (JSON) - 保留並限制 create/update/delete 需授權（簡單示範）
@app.route("/api/posts", methods=["GET"])
def api_list_posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([p.to_dict() for p in posts])

@app.route("/api/posts/<int:post_id>", methods=["GET"])
def api_get_post(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify(post.to_dict())

@app.route("/api/posts", methods=["POST"])
@login_required
def api_create_post():
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not title or not content:
        return jsonify({"error": "title and content required"}), 400
    post = Post(title=title, author_id=current_user.id, content=content)
    db.session.add(post)
    db.session.commit()
    return jsonify(post.to_dict()), 201

@app.route("/api/posts/<int:post_id>", methods=["PUT"])
@login_required
def api_update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    title = data.get("title")
    content = data.get("content")
    if title is not None:
        post.title = title.strip()
    if content is not None:
        post.content = content.strip()
    db.session.commit()
    return jsonify(post.to_dict())

@app.route("/api/posts/<int:post_id>", methods=["DELETE"])
@login_required
def api_delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    db.session.delete(post)
    db.session.commit()
    return "", 204

if __name__ == "__main__":
    app.run(debug=True)