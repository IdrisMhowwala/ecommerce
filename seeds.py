"""
seeds.py — Self-contained seed script. No flask CLI, no PYTHONPATH needed.

Render calls this as:  python seeds.py
Locally run it as:     python seeds.py
"""
import os
import sys

# ── Path fix MUST happen before any project imports ──────────────────────────
# __file__ is always an absolute path when Python runs a named file.
# This inserts the project root (the folder containing seeds.py and app/)
# into sys.path so `import app` works regardless of CWD or PYTHONPATH.
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

# ── Now safe to import project code ──────────────────────────────────────────
from app import create_app                   # noqa: E402
from app.database import get_db             # noqa: E402
from app.auth_utils import hash_password    # noqa: E402

app = create_app()

PRODUCTS = [
    ("Wireless Bluetooth Headphones",
     "Premium noise-cancelling headphones with 30-hour battery life.",
     2999.00, 25,
     "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&q=80"),
    ("Mechanical Keyboard",
     "Tactile RGB mechanical keyboard with Cherry MX switches.",
     4499.00, 15,
     "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400&q=80"),
    ("Smart Watch Series 5",
     "Track fitness, receive notifications, and monitor health.",
     8999.00, 10,
     "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&q=80"),
    ("USB-C Hub 7-in-1",
     "Expand your laptop with HDMI, USB 3.0, SD card, and power delivery.",
     1799.00, 40,
     "https://images.unsplash.com/photo-1625480860249-be231806d936?w=400&q=80"),
    ("Laptop Stand Aluminium",
     "Ergonomic adjustable stand for all 11-17 inch laptops.",
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

with app.app_context():
    db = get_db()

    # Admin user
    if not db.execute("SELECT id FROM users WHERE email=?",
                      ("admin@shop.com",)).fetchone():
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
            ("Admin User", "admin@shop.com", hash_password("admin1234"), "admin"),
        )
        print("Admin created:    admin@shop.com / admin1234")
    else:
        print("Admin exists:     admin@shop.com")

    # Demo customer
    if not db.execute("SELECT id FROM users WHERE email=?",
                      ("user@shop.com",)).fetchone():
        db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
            ("Jane Doe", "user@shop.com", hash_password("user1234"), "customer"),
        )
        print("Customer created: user@shop.com / user1234")
    else:
        print("Customer exists:  user@shop.com")

    # Products
    added = 0
    for name, desc, price, stock, img_url in PRODUCTS:
        if not db.execute("SELECT id FROM products WHERE name=?", (name,)).fetchone():
            db.execute(
                "INSERT INTO products "
                "(name, description, price, stock, image_url, is_active) "
                "VALUES (?,?,?,?,?,?)",
                (name, desc, price, stock, img_url, True),
            )
            added += 1

    db.commit()
    print(f"Products seeded:  {added} added, {len(PRODUCTS)-added} already existed.")
    print("Done.")
