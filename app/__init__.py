import os
from datetime import timedelta
from flask import Flask, render_template
from app.database import get_db, close_db, init_db
from app.auth_utils import get_current_user


# ── Demo seed data ────────────────────────────────────────────────────────────

_SEED_PRODUCTS = [
    ("Wireless Bluetooth Headphones",
     "Premium noise-cancelling headphones with 30-hour battery life.",
     2999.00, 25,
     "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&q=80"),
    ("Mechanical Keyboard",
     "Tactile RGB mechanical keyboard with Cherry MX switches.",
     4499.00, 15,
     "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400&q=80"),
    ("Smart Watch Series 5",
     "Track fitness, receive notifications, and monitor your health.",
     8999.00, 10,
     "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&q=80"),
    ("USB-C Hub 7-in-1",
     "Expand your laptop with HDMI, USB 3.0, SD card and power delivery.",
     1799.00, 40,
     "https://images.unsplash.com/photo-1625480860249-be231806d936?w=400&q=80"),
    ("Laptop Stand Aluminium",
     "Ergonomic adjustable stand compatible with all 11-17 inch laptops.",
     1299.00, 30,
     "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=400&q=80"),
    ("Portable Charger 20000mAh",
     "Fast-charge power bank with dual USB-A and USB-C output.",
     1599.00, 50,
     "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400&q=80"),
    ("Webcam 4K HD",
     "Ultra-clear 4K webcam with autofocus and built-in ring light.",
     3299.00, 20,
     "https://images.unsplash.com/photo-1587826080692-f439cd0b70da?w=400&q=80"),
    ("Desk Lamp LED",
     "Touch-control LED lamp with 5 colour temperatures and USB port.",
     899.00, 35,
     "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=400&q=80"),
]


def _seed(app):
    """
    Idempotent seed: runs on every startup, inserts only what is missing.
    Safe to run against an already-populated database.
    """
    from app.auth_utils import hash_password
    with app.app_context():
        db = get_db()
        try:
            # Admin user
            if not db.execute(
                "SELECT id FROM users WHERE email=?", ("admin@shop.com",)
            ).fetchone():
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role) "
                    "VALUES (?,?,?,?)",
                    ("Admin", "admin@shop.com",
                     hash_password("admin1234"), "admin"),
                )
                print("[seed] admin@shop.com created")

            # Demo customer
            if not db.execute(
                "SELECT id FROM users WHERE email=?", ("user@shop.com",)
            ).fetchone():
                db.execute(
                    "INSERT INTO users (name, email, password_hash, role) "
                    "VALUES (?,?,?,?)",
                    ("Jane Doe", "user@shop.com",
                     hash_password("user1234"), "customer"),
                )
                print("[seed] user@shop.com created")

            # Products
            for name, desc, price, stock, img in _SEED_PRODUCTS:
                if not db.execute(
                    "SELECT id FROM products WHERE name=?", (name,)
                ).fetchone():
                    db.execute(
                        "INSERT INTO products "
                        "(name, description, price, stock, image_url, is_active) "
                        "VALUES (?,?,?,?,?,?)",
                        (name, desc, price, stock, img, True),
                    )

            db.commit()
            print("[seed] done")

        except Exception as exc:
            # Never crash the app over seeding
            print(f"[seed] skipped — {exc}")


# ── Application factory ───────────────────────────────────────────────────────

def create_app(test_config=None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)

    # Load .env when running locally
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Database URL — Render sets DATABASE_URL automatically
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("postgres://"):          # Render still uses old prefix
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if not db_url:                                # local fallback → SQLite
        instance_dir = os.path.join(os.path.dirname(app.root_path), "instance")
        os.makedirs(instance_dir, exist_ok=True)
        db_url = os.path.join(instance_dir, "shop.db")

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
        DATABASE_URL=db_url,
        UPLOAD_FOLDER=os.path.join(app.root_path, "static", "img", "products"),
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    )

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # DB
    app.teardown_appcontext(close_db)
    init_db(app)   # CREATE TABLE IF NOT EXISTS (idempotent)
    _seed(app)     # insert missing rows (idempotent)

    # Template context
    @app.context_processor
    def inject_user():
        return dict(current_user=get_current_user())

    # Error pages
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    # Blueprints
    from app.blueprints.auth.routes  import auth_bp
    from app.blueprints.shop.routes  import shop_bp
    from app.blueprints.admin.routes import admin_bp

    app.register_blueprint(auth_bp,  url_prefix="/auth")
    app.register_blueprint(shop_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
