"""
database.py — PostgreSQL (Render) + SQLite (local dev) unified layer.
"""

import sqlite3
from flask import g, current_app


def _is_postgres(url: str) -> bool:
    return url.startswith("postgres")


def _pg_url(url: str) -> str:
    return url.replace("postgres://", "postgresql://", 1) if url.startswith("postgres://") else url


# ── Cursor wrapper ────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, raw, db_type):
        self._raw     = raw
        self._db_type = db_type

    def fetchone(self):
        row = self._raw.fetchone()
        if row is None:
            return None
        # Wrap postgres RealDictRow so [0] numeric indexing works for COUNT(*) etc.
        if self._db_type == "postgres" and not isinstance(row, _PGRow):
            return _PGRow(row)
        return row

    def fetchall(self):
        rows = self._raw.fetchall()
        if self._db_type == "postgres":
            return [_PGRow(r) for r in rows]
        return rows

    @property
    def lastrowid(self):
        if self._db_type == "postgres":
            # RETURNING id was appended — result is already consumed by fetchone in execute
            return self._raw._lastid
        return self._raw.lastrowid

    @property
    def rowcount(self):
        return self._raw.rowcount


class _PGRow:
    """
    Wraps a psycopg2 RealDictRow to support both dict-style (row["col"])
    and integer-index (row[0]) access — needed for COUNT(*) results.
    """
    def __init__(self, real_dict_row):
        self._row  = real_dict_row
        self._keys = list(real_dict_row.keys()) if real_dict_row else []

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._row[self._keys[key]]
        return self._row[key]

    def __contains__(self, key):
        return key in self._row

    def keys(self):
        return self._keys

    def get(self, key, default=None):
        return self._row.get(key, default)

    def __repr__(self):
        return repr(dict(self._row))


# ── _DB wrapper ───────────────────────────────────────────────────────────────

class _DB:
    def __init__(self, conn, db_type):
        self._conn    = conn
        self._db_type = db_type

    def execute(self, sql: str, params=()):
        if self._db_type == "postgres":
            sql = sql.replace("?", "%s")
            # Append RETURNING id to INSERTs so lastrowid works
            stripped = sql.strip().upper()
            if stripped.startswith("INSERT") and "RETURNING" not in stripped:
                sql = sql.rstrip("; \t\n") + " RETURNING id"
            import psycopg2.extras
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(sql, params or ())
            wrapper = _Cursor(cur, self._db_type)
            # Pre-fetch the RETURNING id row now so the cursor isn't consumed later
            if stripped.startswith("INSERT"):
                row = cur.fetchone()
                wrapper._raw._lastid = row["id"] if row else None
            return wrapper
        else:
            cur = self._conn.cursor()
            cur.execute(sql, params or ())
            return _Cursor(cur, self._db_type)

    def executescript(self, ddl: str):
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


# ── Per-request connection ────────────────────────────────────────────────────

def get_db() -> _DB:
    if "db" not in g:
        url = current_app.config["DATABASE_URL"]
        if _is_postgres(url):
            import psycopg2
            conn = psycopg2.connect(_pg_url(url))
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
    conn = g.pop("db", None)
    g.pop("db_type", None)
    if conn is not None:
        try:
            conn.commit()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


# ── Schema ────────────────────────────────────────────────────────────────────

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
    """Create all tables — idempotent, safe on every boot."""
    with app.app_context():
        url = app.config["DATABASE_URL"]
        if _is_postgres(url):
            import psycopg2
            conn = psycopg2.connect(_pg_url(url))
            conn.autocommit = False
            db = _DB(conn, "postgres")
        else:
            conn = sqlite3.connect(url, detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            db = _DB(conn, "sqlite")
        try:
            ddl = _SCHEMA_POSTGRES if _is_postgres(url) else _SCHEMA_SQLITE
            db.executescript(ddl)
            db.commit()
        finally:
            conn.close()
