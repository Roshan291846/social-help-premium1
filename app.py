import os
import sqlite3
import os
from datetime import datetime, timedelta
from functools import wraps

import razorpay
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(APP_DIR, "social_help.db")

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
razorpay_client = (
    razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else None
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Set COOKIE_SECURE=1 only when deployed over HTTPS.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            subscription_until TEXT
        );
        CREATE TABLE IF NOT EXISTS help_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            issue TEXT NOT NULL,
            details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS payment_intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount_paise INTEGER NOT NULL DEFAULT 10000,
            status TEXT NOT NULL DEFAULT 'pending',
            razorpay_order_id TEXT UNIQUE,
            razorpay_payment_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)

def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("कृपया आधी Login करा.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_user():
    return {"logged_in_user": current_user()}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("नाव, योग्य Email आणि किमान 8 अक्षरांचा Password द्या.", "danger")
            return render_template("register.html")
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password))
                )
            flash("Registration झाले! आता Login करा.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("हा Email आधीच नोंदणीकृत आहे.", "danger")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Login यशस्वी!", "success")
            return redirect(url_for("dashboard"))
        flash("Email किंवा Password चुकीचा आहे.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("तुम्ही Logout झाला आहात.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    with db() as conn:
        requests_list = conn.execute(
            "SELECT * FROM help_requests WHERE user_id = ? ORDER BY id DESC",
            (user["id"],)
        ).fetchall()
    active = bool(user["subscription_until"] and user["subscription_until"] >= datetime.utcnow().date().isoformat())
    return render_template("dashboard.html", user=user, requests_list=requests_list, active=active)

@app.route("/help-request", methods=["GET", "POST"])
@login_required
def help_request():
    if request.method == "POST":
        platform = request.form.get("platform", "")
        issue = request.form.get("issue", "").strip()
        details = request.form.get("details", "").strip()
        if platform not in ("Instagram", "Facebook", "WhatsApp") or not issue or not details:
            flash("सर्व माहिती भरा.", "danger")
        elif len(details) > 2000 or len(issue) > 120:
            flash("माहिती खूप मोठी आहे. कृपया कमी करा.", "danger")
        else:
            with db() as conn:
                conn.execute(
                    "INSERT INTO help_requests (user_id, platform, issue, details, created_at) VALUES (?, ?, ?, ?, ?)",
                    (current_user()["id"], platform, issue, details, datetime.utcnow().isoformat(timespec="minutes"))
                )
            flash("Help Request सबमिट झाली.", "success")
            return redirect(url_for("dashboard"))
    return render_template("help_request.html")

@app.route("/subscription", methods=["GET"])
@login_required
def subscription():
    return render_template(
        "subscription.html",
        razorpay_key_id=RAZORPAY_KEY_ID,
        payment_ready=bool(razorpay_client)
    )

@app.route("/create-payment-order", methods=["POST"])
@login_required
def create_payment_order():
    if not razorpay_client:
        return jsonify({
            "error": "Payment gateway अजून configure केलेला नाही. Server वर Razorpay test keys सेट करा."
        }), 503

    user = current_user()
    amount = 10000  # ₹100 in paise; amount is fixed server-side.
    receipt = f"shp_{user['id']}_{int(datetime.utcnow().timestamp())}"

    try:
        order = razorpay_client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": receipt,
            "notes": {"user_id": str(user["id"]), "plan": "30-day Social Help Premium"}
        })
        with db() as conn:
            conn.execute(
                """INSERT INTO payment_intents
                   (user_id, amount_paise, status, razorpay_order_id, created_at)
                   VALUES (?, ?, 'created', ?, ?)""",
                (user["id"], amount, order["id"], datetime.utcnow().isoformat(timespec="seconds"))
            )
        return jsonify({
            "order_id": order["id"],
            "amount": amount,
            "currency": "INR",
            "key_id": RAZORPAY_KEY_ID,
            "name": "Social Help Premium",
            "description": "30-day membership"
        })
    except Exception:
        app.logger.exception("Could not create Razorpay order")
        return jsonify({"error": "Payment order तयार करता आला नाही. पुन्हा प्रयत्न करा."}), 502

@app.route("/verify-payment", methods=["POST"])
@login_required
def verify_payment():
    if not razorpay_client:
        return jsonify({"error": "Payment gateway configure केलेला नाही."}), 503

    data = request.get_json(silent=True) or {}
    order_id = str(data.get("razorpay_order_id", ""))
    payment_id = str(data.get("razorpay_payment_id", ""))
    signature = str(data.get("razorpay_signature", ""))
    if not order_id or not payment_id or not signature:
        return jsonify({"error": "Payment verification साठी आवश्यक माहिती अपूर्ण आहे."}), 400

    user = current_user()
    with db() as conn:
        order = conn.execute(
            "SELECT * FROM payment_intents WHERE razorpay_order_id = ? AND user_id = ?",
            (order_id, user["id"])
        ).fetchone()

    if not order:
        return jsonify({"error": "हा payment order सापडला नाही."}), 400

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })
        # Fetch from Razorpay and only activate if the payment is captured.
        payment = razorpay_client.payment.fetch(payment_id)
        if payment.get("order_id") != order_id or payment.get("status") != "captured" or int(payment.get("amount", 0)) != 10000:
            return jsonify({"error": "पेमेंट captured/योग्य रकमेचे असल्याची खात्री झाली नाही. कृपया support शी संपर्क करा."}), 400

        today = datetime.utcnow().date()
        current_until = user["subscription_until"]
        if current_until:
            try:
                old_date = datetime.strptime(current_until, "%Y-%m-%d").date()
                if old_date >= today:
                    today = old_date
            except ValueError:
                pass
        until = (today + timedelta(days=30)).isoformat()

        with db() as conn:
            conn.execute(
                """UPDATE payment_intents SET status = 'paid', razorpay_payment_id = ?
                   WHERE id = ? AND status != 'paid'""",
                (payment_id, order["id"])
            )
            conn.execute("UPDATE users SET subscription_until = ? WHERE id = ?", (until, user["id"]))

        return jsonify({"ok": True, "message": f"पेमेंट यशस्वी! Premium {until} पर्यंत सक्रिय आहे."})
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"error": "Payment signature पडताळणी अयशस्वी झाली."}), 400
    except Exception:
        app.logger.exception("Payment verification failed")
        return jsonify({"error": "पेमेंट पडताळता आले नाही. कृपया पुन्हा तपासा."}), 502

@app.route("/admin")
@login_required
@admin_required
def admin():
    with db() as conn:
        requests_list = conn.execute("""
            SELECT help_requests.*, users.name, users.email
            FROM help_requests JOIN users ON users.id = help_requests.user_id
            ORDER BY help_requests.id DESC
        """).fetchall()
        payments = conn.execute("""
            SELECT payment_intents.*, users.name, users.email
            FROM payment_intents JOIN users ON users.id = payment_intents.user_id
            ORDER BY payment_intents.id DESC
        """).fetchall()
    return render_template("admin.html", requests_list=requests_list, payments=payments)

@app.route("/admin/request/<int:request_id>", methods=["POST"])
@login_required
@admin_required
def update_request(request_id):
    status = request.form.get("status", "")
    if status not in ("New", "In progress", "Resolved"):
        abort(400)
    with db() as conn:
        conn.execute("UPDATE help_requests SET status = ? WHERE id = ?", (status, request_id))
    flash("Request status अपडेट झाला.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="ही जागा फक्त Admin साठी आहे."), 403

@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="हे पेज सापडले नाही."), 404

init_db()

if __name__ == "__main__":
    # Local development only. Use a production WSGI server when deploying.
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="127.0.0.1", port=5000)
