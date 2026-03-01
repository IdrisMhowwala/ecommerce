from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, abort)
from app.database import get_db
from app.auth_utils import login_required, get_current_user

shop_bp = Blueprint("shop", __name__)


# ── Cart helpers ──────────────────────────────────────────────────────────────

def get_cart() -> dict:
    return session.get("cart", {})


def save_cart(cart: dict) -> None:
    session["cart"] = cart
    session.modified = True


def cart_item_count() -> int:
    return sum(get_cart().values())


def build_cart_items(db):
    """Resolve cart product_ids to rows; return (items_list, total)."""
    cart  = get_cart()
    items = []
    total = 0.0
    for pid_str, qty in list(cart.items()):
        row = db.execute(
            "SELECT * FROM products WHERE id=? AND is_active=1", (int(pid_str),)
        ).fetchone()
        if row:
            subtotal = float(row["price"]) * qty
            items.append({"product": row, "qty": qty, "subtotal": subtotal})
            total += subtotal
        else:
            cart.pop(pid_str)  # clean stale entries
    save_cart(cart)
    return items, round(total, 2)


# ── Routes ────────────────────────────────────────────────────────────────────

@shop_bp.context_processor
def cart_count():
    return dict(cart_count=cart_item_count())


@shop_bp.route("/")
def index():
    db       = get_db()
    featured = db.execute(
        "SELECT * FROM products WHERE is_active=1 ORDER BY id DESC LIMIT 8"
    ).fetchall()
    return render_template("shop/index.html", featured=featured)


@shop_bp.route("/shop")
def shop():
    db   = get_db()
    page = request.args.get("page", 1, type=int)
    per  = 12
    q    = request.args.get("q", "").strip()

    if q:
        rows = db.execute(
            "SELECT * FROM products WHERE is_active=1 AND (name LIKE ? OR description LIKE ?) ORDER BY name",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM products WHERE is_active=1 ORDER BY id DESC"
        ).fetchall()

    total_count = len(rows)
    products    = rows[(page - 1) * per : page * per]
    total_pages = (total_count + per - 1) // per

    return render_template(
        "shop/products.html",
        products=products,
        page=page,
        total_pages=total_pages,
        q=q,
    )


@shop_bp.route("/product/<int:product_id>")
def product_detail(product_id):
    db  = get_db()
    row = db.execute(
        "SELECT * FROM products WHERE id=? AND is_active=1", (product_id,)
    ).fetchone()
    if not row:
        abort(404)
    return render_template("shop/product_detail.html", product=row)


# ── Cart ──────────────────────────────────────────────────────────────────────

@shop_bp.route("/cart")
def cart():
    db    = get_db()
    items, total = build_cart_items(db)
    return render_template("shop/cart.html", items=items, total=total)


@shop_bp.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    db  = get_db()
    row = db.execute(
        "SELECT * FROM products WHERE id=? AND is_active=1", (product_id,)
    ).fetchone()
    if not row:
        abort(404)

    qty  = max(1, int(request.form.get("quantity", 1)))
    cart = get_cart()
    key  = str(product_id)

    new_qty = cart.get(key, 0) + qty
    if new_qty > row["stock"]:
        flash(f"Only {row['stock']} units of '{row['name']}' in stock.", "warning")
        new_qty = row["stock"]

    if new_qty > 0:
        cart[key] = new_qty
        save_cart(cart)
        flash(f"'{row['name']}' added to cart.", "success")

    return redirect(request.referrer or url_for("shop.shop"))


@shop_bp.route("/cart/update", methods=["POST"])
def update_cart():
    cart = get_cart()
    db   = get_db()

    for key in list(cart.keys()):
        qty_str = request.form.get(f"qty_{key}", "")
        if qty_str.isdigit():
            qty = int(qty_str)
            if qty <= 0:
                cart.pop(key)
            else:
                row = db.execute("SELECT stock FROM products WHERE id=?", (int(key),)).fetchone()
                cart[key] = min(qty, row["stock"]) if row else qty

    save_cart(cart)
    flash("Cart updated.", "info")
    return redirect(url_for("shop.cart"))


@shop_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    flash("Item removed from cart.", "info")
    return redirect(url_for("shop.cart"))


# ── Checkout ──────────────────────────────────────────────────────────────────

@shop_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    db    = get_db()
    items, total = build_cart_items(db)

    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("shop.shop"))

    if request.method == "POST":
        user = get_current_user()

        # Verify stock once more and lock
        errors = []
        for item in items:
            p = db.execute(
                "SELECT * FROM products WHERE id=?", (item["product"]["id"],)
            ).fetchone()
            if not p or p["stock"] < item["qty"]:
                errors.append(
                    f"Sorry, '{item['product']['name']}' only has {p['stock'] if p else 0} units left."
                )

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("shop/checkout.html", items=items, total=total)

        # Create order
        cur = db.execute(
            "INSERT INTO orders (user_id, total_amount, payment_status, order_status) VALUES (?,?,?,?)",
            (user["id"], total, "pending", "placed"),
        )
        order_id = cur.lastrowid

        for item in items:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?,?,?,?)",
                (order_id, item["product"]["id"], item["qty"], float(item["product"]["price"])),
            )
            db.execute(
                "UPDATE products SET stock = stock - ?, updated_at = datetime('now') WHERE id=?",
                (item["qty"], item["product"]["id"]),
            )

        db.commit()
        session.pop("cart", None)
        flash(f"Order #{order_id} placed successfully! We'll notify you when it ships.", "success")
        return redirect(url_for("shop.order_detail", order_id=order_id))

    return render_template("shop/checkout.html", items=items, total=total)


# ── Orders ────────────────────────────────────────────────────────────────────

@shop_bp.route("/orders")
@login_required
def orders():
    user = get_current_user()
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user["id"],)
    ).fetchall()
    return render_template("shop/orders.html", orders=rows)


@shop_bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    user  = get_current_user()
    db    = get_db()
    order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        abort(404)
    if order["user_id"] != user["id"] and user["role"] != "admin":
        abort(403)

    items = db.execute(
        """SELECT oi.*, p.name AS product_name, p.image_url
           FROM order_items oi
           JOIN products p ON p.id = oi.product_id
           WHERE oi.order_id=?""",
        (order_id,),
    ).fetchall()

    return render_template("shop/order_detail.html", order=order, items=items)
