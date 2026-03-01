import os
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, abort)
from werkzeug.utils import secure_filename
from app.database import get_db
from app.auth_utils import admin_required

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file_storage):
    if file_storage and file_storage.filename and allowed_file(file_storage.filename):
        filename = secure_filename(file_storage.filename)
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file_storage.save(path)
        return f"/static/img/products/{filename}"
    return None


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_required
def dashboard():
    db = get_db()

    stats = {
        "products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders":   db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "users":    db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "revenue":  db.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE payment_status='paid'"
        ).fetchone()[0],
        "pending_orders": db.execute(
            "SELECT COUNT(*) FROM orders WHERE order_status='placed'"
        ).fetchone()[0],
    }

    recent_orders = db.execute(
        """SELECT o.*, u.name AS user_name, u.email AS user_email
           FROM orders o JOIN users u ON u.id = o.user_id
           ORDER BY o.created_at DESC LIMIT 10"""
    ).fetchall()

    return render_template("admin/dashboard.html", stats=stats, recent_orders=recent_orders)


# ── Products ──────────────────────────────────────────────────────────────────

@admin_bp.route("/products")
@admin_required
def products():
    db   = get_db()
    rows = db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    return render_template("admin/products.html", products=rows)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def product_new():
    errors = []
    form   = {}

    if request.method == "POST":
        form        = request.form
        name        = form.get("name", "").strip()
        description = form.get("description", "").strip()
        price_str   = form.get("price", "")
        stock_str   = form.get("stock", "0")
        is_active   = True if form.get("is_active") else False

        if not name:
            errors.append("Product name is required.")
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            errors.append("Price must be a valid positive number.")
            price = 0.0
        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            errors.append("Stock must be a valid non-negative integer.")
            stock = 0

        if not errors:
            db        = get_db()
            image_url = save_image(request.files.get("image"))
            db.execute(
                "INSERT INTO products (name, description, price, stock, image_url, is_active) VALUES (?,?,?,?,?,?)",
                (name, description, price, stock, image_url, is_active),
            )
            db.commit()
            flash("Product created successfully.", "success")
            return redirect(url_for("admin.products"))

    return render_template("admin/product_form.html", errors=errors, form=form,
                           title="New Product", product=None)


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_edit(product_id):
    db      = get_db()
    product = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not product:
        abort(404)

    errors = []
    form   = {}

    if request.method == "POST":
        form        = request.form
        name        = form.get("name", "").strip()
        description = form.get("description", "").strip()
        price_str   = form.get("price", "")
        stock_str   = form.get("stock", "0")
        is_active   = True if form.get("is_active") else False

        if not name:
            errors.append("Product name is required.")
        try:
            price = float(price_str)
            if price < 0:
                raise ValueError
        except ValueError:
            errors.append("Price must be a valid positive number.")
            price = float(product["price"])
        try:
            stock = int(stock_str)
            if stock < 0:
                raise ValueError
        except ValueError:
            errors.append("Stock must be a valid non-negative integer.")
            stock = product["stock"]

        if not errors:
            image_url = save_image(request.files.get("image")) or product["image_url"]
            db.execute(
                """UPDATE products
                   SET name=?, description=?, price=?, stock=?, image_url=?, is_active=?
                   WHERE id=?""",
                (name, description, price, stock, image_url, is_active, product_id),
            )
            db.commit()
            flash("Product updated.", "success")
            return redirect(url_for("admin.products"))
    else:
        form = dict(product)

    return render_template("admin/product_form.html", errors=errors, form=form,
                           title="Edit Product", product=product)


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id):
    db = get_db()
    db.execute("UPDATE products SET is_active=FALSE WHERE id=?", (product_id,))
    db.commit()
    flash("Product removed from shop.", "info")
    return redirect(url_for("admin.products"))


# ── Orders ────────────────────────────────────────────────────────────────────

@admin_bp.route("/orders")
@admin_required
def orders():
    db   = get_db()
    rows = db.execute(
        """SELECT o.*, u.name AS user_name, u.email AS user_email
           FROM orders o JOIN users u ON u.id = o.user_id
           ORDER BY o.created_at DESC"""
    ).fetchall()
    return render_template("admin/orders.html", orders=rows)


@admin_bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    db    = get_db()
    order = db.execute(
        "SELECT o.*, u.name AS user_name, u.email AS user_email FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=?",
        (order_id,),
    ).fetchone()
    if not order:
        abort(404)
    items = db.execute(
        "SELECT oi.*, p.name AS product_name FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?",
        (order_id,),
    ).fetchall()
    return render_template("admin/order_detail.html", order=order, items=items)


@admin_bp.route("/orders/<int:order_id>/update", methods=["POST"])
@admin_required
def update_order(order_id):
    db             = get_db()
    order_status   = request.form.get("order_status")
    payment_status = request.form.get("payment_status")

    valid_order   = {"placed", "confirmed", "processing", "shipped", "delivered", "cancelled"}
    valid_payment = {"pending", "paid", "failed", "refunded"}

    updates = []
    params  = []

    if order_status in valid_order:
        updates.append("order_status=?")
        params.append(order_status)
    if payment_status in valid_payment:
        updates.append("payment_status=?")
        params.append(payment_status)

    if updates:
        params.append(order_id)
        db.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id=?", params)
        db.commit()
        flash(f"Order #{order_id} updated.", "success")

    return redirect(url_for("admin.order_detail", order_id=order_id))


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@admin_required
def users():
    db   = get_db()
    rows = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return render_template("admin/users.html", users=rows)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if user:
        new_status = not user["is_active"]
        db.execute("UPDATE users SET is_active=? WHERE id=?", (new_status, user_id))
        db.commit()
        flash(f"User {'activated' if new_status else 'deactivated'}.", "info")
    return redirect(url_for("admin.users"))
