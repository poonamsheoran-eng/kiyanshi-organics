from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import logging
import sys
from datetime import datetime
import time
import uuid
from flask import g
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

app = Flask(__name__)

SENTRY_DSN = os.environ.get('SENTRY_DSN')

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0,  # 100% of transactions for performance monitoring
        environment="production"
    )

# ================= LOGGING CONFIGURATION =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Add request_id to logs
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(g, 'request_id', 'N/A')
        return True

logger.addFilter(RequestIdFilter())

# ================= METRICS TRACKING =================
from collections import defaultdict
import threading
from datetime import datetime

# Global metrics storage (in-memory)
metrics = defaultdict(float)  # Use float to support decimal values
metrics_lock = threading.Lock()  # Thread safety
metrics['app_start_time'] = datetime.now().timestamp()

def track_metric(metric_name, value=1):
    """
    Thread-safe metric tracking
    
    Args:
        metric_name: Name of the metric to track
        value: Amount to add (default 1)
    
    Example:
        track_metric('orders_placed')  # Increment by 1
        track_metric('orders_total_value', 599.99)  # Add specific value
    """
    with metrics_lock:
        metrics[metric_name] += value

def get_all_metrics():
    """Get a snapshot of all metrics (thread-safe)"""
    with metrics_lock:
        # Calculate uptime
        uptime = datetime.now().timestamp() - metrics['app_start_time']
        snapshot = dict(metrics)
        snapshot['uptime_seconds'] = int(uptime)
        snapshot['uptime_hours'] = round(uptime / 3600, 2)
        return snapshot

# ================= CONFIGURATION =================
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
ADMIN_MOBILE = os.environ.get('ADMIN_MOBILE', '9999999999')
DATABASE_URL = os.environ.get('DATABASE_URL')  # Render provides this automatically
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
    """Create PostgreSQL connection"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


def init_db():
    """Initialize PostgreSQL database with tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        mobile VARCHAR(10) UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        unit TEXT NOT NULL
    )
    """)

    # Addresses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS addresses (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        name TEXT,
        mobile VARCHAR(10),
        address_line TEXT NOT NULL,
        city TEXT,
        state TEXT,
        pincode VARCHAR(6)
    )
    """)

    # Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        address_id INTEGER NOT NULL REFERENCES addresses(id),
        total_amount DECIMAL(10, 2) NOT NULL,
        status TEXT DEFAULT 'PLACED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Order items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id),
        product_name TEXT,
        price DECIMAL(10, 2),
        quantity INTEGER,
        unit TEXT
    )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(user_id)")

    conn.commit()
    cursor.close()
    conn.close()


# Initialize database on startup
try:
    init_db()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"⚠️ Database initialization error: {e}")


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

# ================= REQUEST LOGGING MIDDLEWARE =================
@app.before_request
def before_request():
    """Log incoming requests"""
    g.start_time = time.time()
    g.request_id = str(uuid.uuid4())[:8]  # Short request ID
    logger.info(f"Request: {request.method} {request.path}")


@app.after_request
def after_request(response):
    """Log response time and status"""
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        logger.info(
            f"Response: {request.method} {request.path} - "
            f"Status: {response.status_code} - "
            f"Time: {elapsed:.3f}s"
        )
        if response.status_code >= 500:  # ← ADD THESE LINES
            track_metric('errors_5xx')
        elif response.status_code >= 400:
            track_metric('errors_4xx')
    return response

# ================= HEALTH =================
@app.route("/api/health", methods=["GET"])
def health_check():
    logger.info("Health check requested")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        logger.info("Health check passed - database connected")
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# ================= METRICS =================
@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """
    Expose application metrics
    
    Returns real-time metrics about application usage
    """
    logger.info("Metrics requested")
    
    metrics_data = get_all_metrics()
    
    # Calculate derived metrics
    total_logins = metrics_data.get('login_successful', 0) + metrics_data.get('login_failed', 0)
    login_success_rate = 0
    if total_logins > 0:
        login_success_rate = round(
            (metrics_data.get('login_successful', 0) / total_logins) * 100, 
            2
        )
    
    # Calculate conversion rate (orders / product views)
    conversion_rate = 0
    if metrics_data.get('products_viewed', 0) > 0:
        conversion_rate = round(
            (metrics_data.get('orders_placed', 0) / metrics_data.get('products_viewed', 0)) * 100,
            2
        )
    
    # Add calculated metrics
    metrics_data['login_success_rate_percent'] = login_success_rate
    metrics_data['conversion_rate_percent'] = conversion_rate
    
    return jsonify(metrics_data), 200

# ================= AUTH =================
@app.route("/api/auth", methods=["POST"])
def auth():
    logger.info("Authentication attempt")
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
    cursor.execute("SELECT password FROM users WHERE mobile=%s", (mobile,))
    user = cursor.fetchone()

    if not user:
        hashed = generate_password_hash(password)
        cursor.execute("INSERT INTO users (mobile, password) VALUES (%s, %s)", (mobile, hashed))
        conn.commit()
        cursor.close()
        conn.close()
        role = "admin" if mobile == ADMIN_MOBILE else "customer"
        logger.info(f"New account created for mobile: {mobile[-4:]}**** - Role: {role}")
        return jsonify({"message": "Account created", "role": role}), 201

    if check_password_hash(user["password"], password):
        cursor.close()
        conn.close()
        role = "admin" if mobile == ADMIN_MOBILE else "customer"
        logger.info(f"Login successful for mobile: {mobile[-4:]}**** - Role: {role}")
        track_metric('login_successful')
        return jsonify({"message": "Login successful", "role": role}), 200

    cursor.close()
    conn.close()
    logger.warning(f"Failed login attempt for mobile: {mobile[-4:]}****")
    track_metric('login_failed')
    return jsonify({"error": "Invalid credentials"}), 401


# ================= PRODUCTS =================
@app.route("/api/products", methods=["GET"])
def get_products():
    logger.info("Fetching all products")
    track_metric('products_viewed')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY id")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info(f"Successfully fetched {len(rows)} products")
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        logger.error(f"Error fetching products: {str(e)}")
        return jsonify({"error": "Failed to fetch products"}), 500


@app.route("/api/admin/products", methods=["POST"])
@admin_required
def add_product():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products (name, quantity, price, unit) VALUES (%s, %s, %s, %s)",
        (data["name"], data["quantity"], data["price"], data["unit"])
    )
    conn.commit()
    cursor.close()
    conn.close()
    track_metric('products_added')
    return jsonify({"message": "Product added"}), 201


@app.route("/api/admin/products/<int:product_id>", methods=["PUT"])
@admin_required
def update_product(product_id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE products SET name=%s, quantity=%s, price=%s, unit=%s WHERE id=%s",
        (data["name"], data["quantity"], data["price"], data["unit"], product_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    track_metric('products_updated')
    return jsonify({"message": "Product updated"}), 200


@app.route("/api/admin/products/<int:product_id>", methods=["DELETE"])
@admin_required
def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id=%s", (product_id,))
    conn.commit()
    cursor.close()
    conn.close()
    track_metric('products_deleted')
    return jsonify({"message": "Product deleted"}), 200


# ================= ADDRESSES =================
@app.route("/api/addresses/<mobile>", methods=["GET"])
def get_addresses(mobile):
    if not validate_mobile(mobile):
        return jsonify({"error": "Invalid mobile number"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify([]), 200

    cursor.execute("""
        SELECT id, name, mobile, address_line, city, state, pincode
        FROM addresses WHERE user_id=%s
    """, (user['id'],))

    rows = cursor.fetchall()
    cursor.close()
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
    cursor.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    user_id = user['id']
    cursor.execute("""
        INSERT INTO addresses
        (user_id, name, mobile, address_line, city, state, pincode)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        user_id,
        data.get("name"),
        mobile,
        address_line,
        data.get("city"),
        data.get("state"),
        data.get("pincode")
    ))

    address_id = cursor.fetchone()['id']
    conn.commit()
    cursor.close()
    conn.close()
    track_metric('addresses_added')
    return jsonify({"message": "Address saved successfully", "id": address_id}), 201


# ================= ORDERS =================
@app.route("/api/order", methods=["POST"])
def place_order():
    logger.info("Order placement initiated")
    data = request.get_json()
    mobile = data.get("mobile")
    address_id = data.get("address_id")
    cart = data.get("cart")

    if not mobile or not address_id or not cart:
        return jsonify({"error": "Invalid order data"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify({"error": "User not found"}), 404

    user_id = user['id']
    total = sum(item["price"] * item["quantity"] for item in cart)

    cursor.execute("""
        INSERT INTO orders (user_id, address_id, total_amount)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (user_id, address_id, total))

    order_id = cursor.fetchone()['id']

    for item in cart:
        cursor.execute("""
            INSERT INTO order_items
            (order_id, product_name, price, quantity, unit)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            order_id,
            item["name"],
            item["price"],
            item["quantity"],
            item["unit"]
        ))

    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"Order placed successfully - Order ID: {order_id}, Total: ₹{total:.2f}")
    track_metric('orders_placed')
    track_metric('orders_total_value', total)
    return jsonify({"message": "Order placed", "order_id": order_id}), 201


@app.route("/api/my-orders/<mobile>", methods=["GET"])
def my_orders(mobile):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        conn.close()
        return jsonify([]), 200

    user_id = user['id']
    cursor.execute("""
        SELECT o.id, o.total_amount, o.status, o.created_at,
               a.address_line, a.city
        FROM orders o
        JOIN addresses a ON o.address_id = a.id
        WHERE o.user_id=%s
        ORDER BY o.id DESC
    """, (user_id,))

    orders = cursor.fetchall()
    result = []

    for order in orders:
        order_id = order['id']
        cursor.execute("""
            SELECT product_name, price, quantity, unit
            FROM order_items
            WHERE order_id=%s
        """, (order_id,))
        items = cursor.fetchall()

        result.append({
            "id": order['id'],
            "total_amount": float(order['total_amount']),
            "status": order['status'],
            "created_at": order['created_at'].isoformat() if order['created_at'] else None,
            "address_line": order['address_line'],
            "city": order['city'],
            "items": [dict(item) for item in items]
        })

    cursor.close()
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
            WHERE order_id=%s
        """, (order_id,))
        items_raw = cursor.fetchall()

        result.append({
            "order_id": order['id'],
            "mobile": order['mobile'],
            "total_amount": float(order['total_amount']),
            "status": order['status'],
            "created_at": order['created_at'].isoformat() if order['created_at'] else None,
            "address": {
                "name": order['name'],
                "address_line": order['address_line'],
                "city": order['city'],
                "state": order['state'],
                "pincode": order['pincode']
            },
            "items": [dict(item) for item in items_raw]
        })

    cursor.close()
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
        "UPDATE orders SET status=%s WHERE id=%s",
        (status, order_id)
    )

    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({"error": "Order not found"}), 404

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Status updated"}), 200


@app.route("/api/test-error")
def test_error():
    logger.error("Testing Sentry error tracking")
    raise Exception("This is a test error!")

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


