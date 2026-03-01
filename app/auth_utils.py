"""
auth_utils.py — Password hashing and session-based auth helpers.
"""
import hashlib
import hmac
import os
import secrets
from functools import wraps

from flask import session, redirect, url_for, flash, abort, g

from app.database import get_db


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return a salted SHA-256 hash string: 'sha256$<salt>$<hex_digest>'."""
    salt = secrets.token_hex(16)
    digest = _pbkdf2(password, salt)
    return f"sha256${salt}${digest}"


def check_password(password: str, stored_hash: str) -> bool:
    """Verify *password* against a stored hash produced by hash_password()."""
    try:
        algo, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    expected = _pbkdf2(password, salt)
    return hmac.compare_digest(expected, digest)


def _pbkdf2(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return dk.hex()


# ── Session helpers ───────────────────────────────────────────────────────────

def login_user(user_row) -> None:
    session.clear()
    session["user_id"] = user_row["id"]
    session["user_role"] = user_row["role"]
    session.permanent = True


def logout_user() -> None:
    session.clear()


def get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


# ── Decorators ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please log in.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("user_role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated
