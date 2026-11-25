from datetime import datetime
import os
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(BASE_DIR, 'blog.db')}")
app.config["SECRET_KEY"] = "replace-with-a-strong-secret-key"

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if os.path.isfile(app.config["UPLOAD_FOLDER"]):
  os.remove(app.config["UPLOAD_FOLDER"])
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "この操作を行うにはログインしてください。"


def allowed_file(filename):
  return (
      "." in filename
      and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
  )


def save_uploaded_image(file):
  if file and file.filename != "" and allowed_file(file.filename):
    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else "jpg"
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(save_path)
    return unique_name
  return None


def delete_image_file(filename):
  if filename:
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.isfile(file_path):
      os.remove(file_path)


class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(80), unique=True, nullable=False)
  password_hash = db.Column(db.String(255), nullable=False)
  posts = db.relationship("Post", backref="author", lazy=True)

  def set_password(self, password):
    self.password_hash = generate_password_hash(password)

  def check_password(self, password):
    return check_password_hash(self.password_hash, password)


class Post(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  title = db.Column(db.String(100), nullable=False)
  body = db.Column(db.Text, nullable=False)
  image_filename = db.Column(db.String(255), nullable=True)
  created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
  user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))


with app.app_context():
  db.create_all()
  if not User.query.filter_by(username="admin").first():
    admin_user = User(username="admin")
    admin_user.set_password("admin1234")
    db.session.add(admin_user)
    db.session.commit()


@app.route("/")
def index():
  posts = Post.query.order_by(Post.created_at.desc()).all()
  return render_template("index.html", posts=posts)


@app.route("/post/<int:post_id>")
def detail(post_id):
  post = Post.query.get_or_404(post_id)
  return render_template("detail.html", post=post)


@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
  if request.method == "POST":
    title = request.form["title"]
    body = request.form["body"]
    image_filename = save_uploaded_image(request.files.get("image"))

    new_post = Post(
        title=title,
        body=body,
        image_filename=image_filename,
        user_id=current_user.id,
    )
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for("index"))

  return render_template("create.html")


@app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def edit(post_id):
  post = Post.query.get_or_404(post_id)
  if post.user_id != current_user.id:
    abort(403)

  if request.method == "POST":
    post.title = request.form["title"]
    post.body = request.form["body"]

    new_image = save_uploaded_image(request.files.get("image"))
    if new_image:
      delete_image_file(post.image_filename)
      post.image_filename = new_image

    db.session.commit()
    return redirect(url_for("detail", post_id=post.id))

  return render_template("edit.html", post=post)


@app.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete(post_id):
  post = Post.query.get_or_404(post_id)
  if post.user_id != current_user.id:
    abort(403)

  delete_image_file(post.image_filename)
  db.session.delete(post)
  db.session.commit()
  return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
  if current_user.is_authenticated:
    return redirect(url_for("index"))

  if request.method == "POST":
    username = request.form["username"].strip()
    password = request.form["password"]
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
      login_user(user)
      next_page = request.args.get("next")
      return redirect(next_page or url_for("index"))

    flash("ユーザー名またはパスワードが正しくありません。")

  return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
  if current_user.is_authenticated:
    return redirect(url_for("index"))

  if request.method == "POST":
    username = request.form["username"].strip()
    password = request.form["password"]

    if not username or not password:
      flash("ユーザー名とパスワードの両方を入力してください。")
      return render_template("register.html")

    if User.query.filter_by(username=username).first():
      flash("そのユーザー名はすでに使われています。")
      return render_template("register.html")

    new_user = User(username=username)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)
    flash("個人アカウントを作成し、ログインしました。")
    return redirect(url_for("index"))

  return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
  logout_user()
  return redirect(url_for("index"))


if __name__ == "__main__":
  app.run(debug=True)