from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# ================= CONFIGURATION =================
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
ADMIN_MOBILE = os.environ.get('ADMIN_MOBILE', '9999999999')
DB_NAME = os.environ.get('DB_NAME', 'users.db')
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(',')

CORS(app, resources={
    r"/api/*": {
        "origins": ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Mobile"]
    }
})

app.config['SECRET_KEY'] = SECRET_KEY


# ================= DATABASE =================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mobile TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        unit TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT,
        mobile TEXT,
        address_line TEXT NOT NULL,
        city TEXT,
        state TEXT,
        pincode TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        address_id INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'PLACED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (address_id) REFERENCES addresses(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_name TEXT,
        price REAL,
        quantity INTEGER,
        unit TEXT,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(user_id)")

    conn.commit()
    conn.close()


init_db()


# ================= UTILITIES =================
def validate_mobile(mobile):
    return mobile and isinstance(mobile, str) and len(mobile) == 10 and mobile.isdigit()


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        mobile = None

        if request.is_json:
            data = request.get_json(silent=True) or {}
            mobile = data.get('mobile')

        if not mobile:
            mobile = kwargs.get('mobile')

        if not mobile:
            mobile = request.headers.get('Mobile')

        if mobile != ADMIN_MOBILE:
            return jsonify({"error": "Unauthorized access"}), 403

        return f(*args, **kwargs)

    return decorated_function


# ================= HEALTH =================
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200


# ================= AUTH =================
@app.route("/api/auth", methods=["POST"])
def auth():
    data = request.get_json()
    mobile = data.get("mobile")
    password = data.get("password")

    if not mobile or not password:
        return jsonify({"error": "Mobile and password required"}), 400

    if not validate_mobile(mobile):
        return jsonify({"error": "Invalid mobile number"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE mobile=?", (mobile,))
    user = cursor.fetchone()

    if not user:
        hashed = generate_password_hash(password)
        cursor.execute("INSERT INTO users (mobile, password) VALUES (?, ?)", (mobile, hashed))
        conn.commit()
        conn.close()
        role = "admin" if mobile == ADMIN_MOBILE else "customer"
        return jsonify({"message": "Account created", "role": role}), 201

    if check_password_hash(user["password"], password):
        conn.close()
        role = "admin" if mobile == ADMIN_MOBILE else "customer"
        return jsonify({"message": "Login successful", "role": role}), 200

    conn.close()
    return jsonify({"error": "Invalid credentials"}), 401


# ================= PRODUCTS =================
@app.route("/api/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200


@app.route("/api/admin/products", methods=["POST"])
@admin_required
def add_product():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, quantity, price, unit) VALUES (?, ?, ?, ?)",
        (data["name"], data["quantity"], data["price"], data["unit"])
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Product added"}), 201


@app.route("/api/admin/products/<int:product_id>", methods=["PUT"])
@admin_required
def update_product(product_id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE products SET name=?, quantity=?, price=?, unit=? WHERE id=?",
        (data["name"], data["quantity"], data["price"], data["unit"], product_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Product updated"}), 200


@app.route("/api/admin/products/<int:product_id>", methods=["DELETE"])
@admin_required
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Product deleted"}), 200


# ================= ADDRESSES =================
@app.route("/api/addresses/<mobile>", methods=["GET"])
def get_addresses(mobile):
    if not validate_mobile(mobile):
        return jsonify({"error": "Invalid mobile number"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify([]), 200

    cursor.execute("""
        SELECT id, name, mobile, address_line, city, state, pincode
        FROM addresses WHERE user_id=?
    """, (user['id'],))

    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200


@app.route("/api/address", methods=["POST"])
def add_address():
    data = request.get_json()
    mobile = data.get("mobile")

    if not mobile or not validate_mobile(mobile):
        return jsonify({"error": "Valid mobile number required"}), 400

    address_line = data.get("address_line")
    if not address_line:
        return jsonify({"error": "Address line is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    user_id = user['id']
    cursor.execute("""
        INSERT INTO addresses
        (user_id, name, mobile, address_line, city, state, pincode)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        data.get("name"),
        mobile,
        address_line,
        data.get("city"),
        data.get("state"),
        data.get("pincode")
    ))

    conn.commit()
    address_id = cursor.lastrowid
    conn.close()
    return jsonify({"message": "Address saved successfully", "id": address_id}), 201


# ================= ORDERS =================
@app.route("/api/order", methods=["POST"])
def place_order():
    data = request.get_json()
    mobile = data.get("mobile")
    address_id = data.get("address_id")
    cart = data.get("cart")

    if not mobile or not address_id or not cart:
        return jsonify({"error": "Invalid order data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    user_id = user['id']
    total = sum(item["price"] * item["quantity"] for item in cart)

    cursor.execute("""
        INSERT INTO orders (user_id, address_id, total_amount)
        VALUES (?, ?, ?)
    """, (user_id, address_id, total))

    order_id = cursor.lastrowid

    for item in cart:
        cursor.execute("""
            INSERT INTO order_items
            (order_id, product_name, price, quantity, unit)
            VALUES (?, ?, ?, ?, ?)
        """, (
            order_id,
            item["name"],
            item["price"],
            item["quantity"],
            item["unit"]
        ))

    conn.commit()
    conn.close()
    return jsonify({"message": "Order placed", "order_id": order_id}), 201


@app.route("/api/my-orders/<mobile>", methods=["GET"])
def my_orders(mobile):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=?", (mobile,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify([]), 200

    user_id = user['id']
    cursor.execute("""
        SELECT o.id, o.total_amount, o.status, o.created_at,
               a.address_line, a.city
        FROM orders o
        JOIN addresses a ON o.address_id = a.id
        WHERE o.user_id=?
        ORDER BY o.id DESC
    """, (user_id,))

    orders = cursor.fetchall()
    result = []

    for order in orders:
        order_id = order['id']
        cursor.execute("""
            SELECT product_name, price, quantity, unit
            FROM order_items
            WHERE order_id=?
        """, (order_id,))
        items = cursor.fetchall()

        result.append({
            "id": order['id'],
            "total_amount": order['total_amount'],
            "status": order['status'],
            "created_at": order['created_at'],
            "address_line": order['address_line'],
            "city": order['city'],
            "items": [dict(item) for item in items]
        })

    conn.close()
    return jsonify(result), 200


@app.route("/api/admin/orders/<mobile>", methods=["GET"])
@admin_required
def admin_orders(mobile):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, u.mobile, o.total_amount, o.status, o.created_at,
               a.name, a.address_line, a.city, a.state, a.pincode
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN addresses a ON o.address_id = a.id
        ORDER BY o.id DESC
    """)

    orders = cursor.fetchall()
    result = []

    for order in orders:
        order_id = order['id']
        cursor.execute("""
            SELECT product_name, price, quantity, unit
            FROM order_items
            WHERE order_id=?
        """, (order_id,))
        items_raw = cursor.fetchall()

        result.append({
            "order_id": order['id'],
            "mobile": order['mobile'],
            "total_amount": order['total_amount'],
            "status": order['status'],
            "created_at": order['created_at'],
            "address": {
                "name": order['name'],
                "address_line": order['address_line'],
                "city": order['city'],
                "state": order['state'],
                "pincode": order['pincode']
            },
            "items": [dict(item) for item in items_raw]
        })

    conn.close()
    return jsonify(result), 200


@app.route("/api/admin/order/status", methods=["PUT"])
@admin_required
def update_order_status():
    data = request.get_json()

    order_id = data.get("order_id")
    status = data.get("status")

    if not order_id or not status:
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status=? WHERE id=?",
        (status, order_id)
    )

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    conn.commit()
    conn.close()

    return jsonify({"message": "Status updated"}), 200


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
