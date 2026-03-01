"""
seeds.py — Seed demo data into whatever database is configured.

Local SQLite:   python seeds.py
Render Postgres: DATABASE_URL=<your-render-url> python seeds.py
"""
import os
import sys

# Ensure the project root is always on sys.path regardless of how/where
# this script is invoked (handles Render's working directory behaviour).
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.database import get_db
from app.auth_utils import hash_password

app = create_app()

with app.app_context():
    db = get_db()

    # ── Users ─────────────────────────────────────────────────────────────────
    existing = db.execute("SELECT id FROM users WHERE email=?", ("admin@shop.com",)).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
            ("Admin User", "admin@shop.com", hash_password("admin1234"), "admin"),
        )
        print("✅ Admin created: admin@shop.com / admin1234")
    else:
        print("ℹ️  Admin already exists.")

    if not db.execute("SELECT id FROM users WHERE email=?", ("user@shop.com",)).fetchone():
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
            ("Jane Doe", "user@shop.com", hash_password("user1234"), "customer"),
        )
        print("✅ Customer created: user@shop.com / user1234")

    # ── Products ──────────────────────────────────────────────────────────────
    products = [
        ("Wireless Bluetooth Headphones",
         "Premium noise-cancelling headphones with 30-hour battery life and foldable design.",
         2999.00, 25,
         "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&q=80"),
        ("Mechanical Keyboard",
         "Tactile RGB mechanical keyboard with Cherry MX switches, perfect for gaming and coding.",
         4499.00, 15,
         "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400&q=80"),
        ("Smart Watch Series 5",
         "Track fitness, receive notifications, and monitor health with our flagship smartwatch.",
         8999.00, 10,
         "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&q=80"),
        ("USB-C Hub 7-in-1",
         "Expand your laptop connectivity with HDMI, USB 3.0, SD card, and power delivery.",
         1799.00, 40,
         "https://images.unsplash.com/photo-1625480860249-be231806d936?w=400&q=80"),
        ("Laptop Stand Aluminium",
         "Ergonomic adjustable aluminium laptop stand compatible with all 11-17 inch laptops.",
         1299.00, 30,
         "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=400&q=80"),
        ("Portable Charger 20000mAh",
         "Fast-charge power bank with dual USB-A and USB-C output. Charges phone 5 times.",
         1599.00, 50,
         "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=400&q=80"),
        ("Webcam 4K HD",
         "Ultra-clear 4K webcam with autofocus and built-in ring light for professional calls.",
         3299.00, 20,
         "https://images.unsplash.com/photo-1587826080692-f439cd0b70da?w=400&q=80"),
        ("Desk Lamp LED",
         "Touch-control LED desk lamp with 5 colour temperatures, USB charging port, and dimmer.",
         899.00, 35,
         "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=400&q=80"),
    ]

    added = 0
    for name, desc, price, stock, img_url in products:
        if not db.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone():
            db.execute(
                "INSERT INTO products (name, description, price, stock, image_url, is_active) "
                "VALUES (?,?,?,?,?,?)",
                (name, desc, price, stock, img_url, True),
            )
            added += 1

    db.commit()
    print(f"✅ {added} demo products added ({len(products)-added} already existed).")
    print()
    print("🚀  Start the app:  python run.py   or   flask run")
    print("    Admin login:    admin@shop.com / admin1234")
    print("    User  login:    user@shop.com  / user1234")
