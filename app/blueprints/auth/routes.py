from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from app.database import get_db
from app.auth_utils import hash_password, check_password, login_user, logout_user, login_required

auth_bp = Blueprint("auth", __name__)


# ── Validation helpers ────────────────────────────────────────────────────────
def validate_register(name, email, password, confirm):
    errors = []
    if not name or len(name.strip()) < 2:
        errors.append("Name must be at least 2 characters.")
    if not email or "@" not in email:
        errors.append("A valid email is required.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm:
        errors.append("Passwords do not match.")
    return errors


def validate_login(email, password):
    errors = []
    if not email:
        errors.append("Email is required.")
    if not password:
        errors.append("Password is required.")
    return errors


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))

    errors = []
    form = {}

    if request.method == "POST":
        form = request.form
        name    = form.get("name", "").strip()
        email   = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm  = form.get("confirm", "")

        errors = validate_register(name, email, password, confirm)

        if not errors:
            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if existing:
                errors.append("An account with that email already exists.")
            else:
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
                    (name, email, hash_password(password), "customer"),
                )
                db.commit()
                flash("Account created! Please sign in.", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/register.html", errors=errors, form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))

    errors = []
    form = {}

    if request.method == "POST":
        form  = request.form
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")

        errors = validate_login(email, password)

        if not errors:
            db   = get_db()
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if user and user["is_active"] and check_password(password, user["password_hash"]):
                login_user(user)
                next_url = request.args.get("next") or url_for("shop.index")
                flash(f"Welcome back, {user['name']}!", "success")
                return redirect(next_url)
            else:
                errors.append("Invalid email or password.")

    return render_template("auth/login.html", errors=errors, form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("shop.index"))
