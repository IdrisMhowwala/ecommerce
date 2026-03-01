"""
database.py — Unified DB layer supporting PostgreSQL (Render) and SQLite (local dev).

PostgreSQL is used when DATABASE_URL starts with 'postgres'.
SQLite is the automatic fallback for local development.

Public API  (identical regardless of backend):
    get_db()        → _DB wrapper
    close_db(e)     → teardown_appcontext hook
    init_db(app)    → idempotent schema creation
"""

import os
import sqlite3
from flask import g, current_app


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_postgres(url: str) -> bool:
    return url.startswith("postgres")


def _fix_pg_url(url: str) -> str:
    """Render supplies postgres:// — psycopg2 requires postgresql://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Cursor wrapper
# ─────────────────────────────────────────────────────────────────────────────

class _Cursor:
    """Normalises psycopg2 / sqlite3 cursor APIs."""

    def __init__(self, raw, db_type: str):
        self._raw     = raw
        self._db_type = db_type

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()

    @property
    def lastrowid(self):
        if self._db_type == "postgres":
            row = self._raw.fetchone()
            if row is None:
                return None
            # RealDictRow → dict access; plain row → index 0
            try:
                return row["id"]
            except (KeyError, TypeError):
                return row[0]
        return self._raw.lastrowid

    @property
    def rowcount(self):
        return self._raw.rowcount


# ─────────────────────────────────────────────────────────────────────────────
# Connection wrapper  (_DB)
# ─────────────────────────────────────────────────────────────────────────────

class _DB:
    """
    Wraps a raw DB connection and exposes .execute() with:
      - ? placeholders (converted to %s for postgres automatically)
      - dict-like rows (RealDictCursor for pg; sqlite3.Row for sqlite)
      - .lastrowid working correctly for INSERT on both backends
    """

    def __init__(self, conn, db_type: str):
        self._conn    = conn
        self._db_type = db_type

    # -- internal --

    def _adapt(self, sql: str, params):
        if self._db_type == "postgres":
            sql = sql.replace("?", "%s")
        return sql, params

    def _cursor(self):
        if self._db_type == "postgres":
            import psycopg2.extras
            return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        return self._conn.cursor()

    # -- public --

    def execute(self, sql: str, params=()):
        sql, params = self._adapt(sql, params)

        # For postgres INSERTs we need RETURNING id so lastrowid works
        if self._db_type == "postgres":
            stripped = sql.strip().upper()
            if stripped.startswith("INSERT") and "RETURNING" not in stripped:
                sql = sql.rstrip("; \t\n") + " RETURNING id"

        cur = self._cursor()
        cur.execute(sql, params or ())
        return _Cursor(cur, self._db_type)

    def executescript(self, ddl: str):
        """Run multi-statement DDL (CREATE TABLE …)."""
        if self._db_type == "postgres":
            cur = self._conn.cursor()
            for stmt in (s.strip() for s in ddl.split(";") if s.strip()):
                cur.execute(stmt)
        else:
            self._conn.executescript(ddl)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Per-request connection
# ─────────────────────────────────────────────────────────────────────────────

def get_db() -> _DB:
    if "db" not in g:
        url = current_app.config["DATABASE_URL"]

        if _is_postgres(url):
            import psycopg2
            conn = psycopg2.connect(_fix_pg_url(url))
            conn.autocommit = False
            g.db      = conn
            g.db_type = "postgres"
        else:
            conn = sqlite3.connect(url, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            g.db      = conn
            g.db_type = "sqlite"

    return _DB(g.db, g.db_type)


def close_db(e=None):
    conn    = g.pop("db", None)
    db_type = g.pop("db_type", "sqlite")
    if conn is not None:
        try:
            conn.commit()
        except Exception:
            pass
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Schema — separate DDL for each backend
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'customer',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    price       REAL    NOT NULL,
    image_url   TEXT,
    stock       INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    total_amount        REAL    NOT NULL DEFAULT 0,
    payment_status      TEXT    NOT NULL DEFAULT 'pending',
    order_status        TEXT    NOT NULL DEFAULT 'placed',
    razorpay_order_id   TEXT    UNIQUE,
    razorpay_payment_id TEXT    UNIQUE,
    razorpay_signature  TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT
);
CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id)   ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity   INTEGER NOT NULL DEFAULT 1,
    price      REAL    NOT NULL,
    UNIQUE(order_id, product_id),
    CHECK(quantity > 0),
    CHECK(price >= 0)
);
CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_user     ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_ord ON order_items(order_id);
"""

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          TEXT        NOT NULL,
    email         TEXT        NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,
    role          TEXT        NOT NULL DEFAULT 'customer',
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    name        TEXT          NOT NULL,
    description TEXT          NOT NULL DEFAULT '',
    price       NUMERIC(12,2) NOT NULL,
    image_url   TEXT,
    stock       INTEGER       NOT NULL DEFAULT 0,
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS orders (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER       NOT NULL REFERENCES users(id),
    total_amount        NUMERIC(12,2) NOT NULL DEFAULT 0,
    payment_status      TEXT          NOT NULL DEFAULT 'pending',
    order_status        TEXT          NOT NULL DEFAULT 'placed',
    razorpay_order_id   TEXT UNIQUE,
    razorpay_payment_id TEXT UNIQUE,
    razorpay_signature  TEXT,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INTEGER       NOT NULL REFERENCES orders(id)   ON DELETE CASCADE,
    product_id INTEGER       NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity   INTEGER       NOT NULL DEFAULT 1,
    price      NUMERIC(12,2) NOT NULL,
    UNIQUE(order_id, product_id),
    CHECK(quantity > 0),
    CHECK(price >= 0)
);
CREATE INDEX IF NOT EXISTS idx_users_email     ON users(email);
CREATE INDEX IF NOT EXISTS idx_orders_user     ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_ord ON order_items(order_id);
"""


def init_db(app):
    """Create all tables (idempotent — safe to run on every deploy)."""
    with app.app_context():
        db  = get_db()
        url = app.config["DATABASE_URL"]
        ddl = _SCHEMA_POSTGRES if _is_postgres(url) else _SCHEMA_SQLITE
        db.executescript(ddl)
        db.commit()
