import os, sqlite3, secrets, hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "payments.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# The merchant's PUBLIC receiving addresses are configured by the site owner.
# Never put seed phrases, private keys, or signing keys in this application.
COINS = {
    "ETH": {"name": "Ethereum", "network": "Ethereum", "address_env": "WALLET_ETH"},
    "BNB": {"name": "BNB", "network": "BNB Smart Chain", "address_env": "WALLET_BNB"},
    "SOL": {"name": "Solana", "network": "Solana", "address_env": "WALLET_SOL"},
    "BTC": {"name": "Bitcoin", "network": "Bitcoin", "address_env": "WALLET_BTC"},
    "USDT_ETH": {"name": "Tether USD", "network": "Ethereum (ERC-20)", "address_env": "WALLET_USDT_ETH"},
    "USDT_BNB": {"name": "Tether USD", "network": "BNB Smart Chain (BEP-20)", "address_env": "WALLET_USDT_BNB"},
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            description TEXT NOT NULL,
            amount TEXT NOT NULL,
            currency TEXT NOT NULL,
            network TEXT NOT NULL,
            address TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            tx_hash TEXT,
            created_at TEXT NOT NULL,
            customer_note TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS admin (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )""")
        row = c.execute("SELECT username FROM admin WHERE username=?", (ADMIN_USER,)).fetchone()
        if not row and ADMIN_PASSWORD:
            c.execute("INSERT INTO admin(username,password_hash) VALUES(?,?)",
                      (ADMIN_USER, generate_password_hash(ADMIN_PASSWORD)))

init_db()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

@app.get("/")
def home():
    if session.get("admin"):
        return redirect(url_for("dashboard"))
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as c:
            row = c.execute("SELECT * FROM admin WHERE username=?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session.clear()
            session["admin"] = username
            return redirect(url_for("dashboard"))
        flash("Identifiants incorrects.")
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.get("/admin")
@login_required
def dashboard():
    with db() as c:
        invoices = c.execute("SELECT * FROM invoices ORDER BY id DESC LIMIT 100").fetchall()
    return render_template("dashboard.html", invoices=invoices, coins=COINS)

@app.route("/admin/create", methods=["GET", "POST"])
@login_required
def create_invoice():
    configured = {}
    for code, meta in COINS.items():
        addr = os.environ.get(meta["address_env"], "").strip()
        if addr:
            configured[code] = {**meta, "address": addr}
    if request.method == "POST":
        description = request.form.get("description", "").strip()[:120]
        amount = request.form.get("amount", "").strip()
        currency = request.form.get("currency", "")
        try:
            if not amount or float(amount) <= 0 or len(amount) > 30:
                raise ValueError()
        except ValueError:
            flash("Entre un montant positif valide.")
            return render_template("create.html", configured=configured)
        if currency not in configured:
            flash("Cette devise n'a pas d'adresse de réception configurée.")
            return render_template("create.html", configured=configured)
        meta = configured[currency]
        token = secrets.token_urlsafe(24)
        created = datetime.now(timezone.utc).isoformat()
        with db() as c:
            c.execute("""INSERT INTO invoices(token,description,amount,currency,network,address,status,created_at)
                         VALUES(?,?,?,?,?,?,?,?)""",
                      (token, description or "Paiement", amount, currency, meta["network"], meta["address"], "pending", created))
        return render_template("created.html", link=url_for("invoice", token=token, _external=True))
    return render_template("create.html", configured=configured)

@app.get("/pay/<token>")
def invoice(token):
    with db() as c:
        inv = c.execute("SELECT * FROM invoices WHERE token=?", (token,)).fetchone()
    if not inv:
        abort(404)
    return render_template("invoice.html", inv=inv)

@app.post("/pay/<token>/submit")
def submit_tx(token):
    tx_hash = request.form.get("tx_hash", "").strip()[:180]
    note = request.form.get("customer_note", "").strip()[:300]
    if not tx_hash:
        flash("Ajoute l'identifiant de transaction après avoir envoyé le paiement.")
        return redirect(url_for("invoice", token=token))
    with db() as c:
        inv = c.execute("SELECT * FROM invoices WHERE token=?", (token,)).fetchone()
        if not inv:
            abort(404)
        if inv["status"] == "pending":
            c.execute("UPDATE invoices SET tx_hash=?, customer_note=? WHERE token=?",
                      (tx_hash, note, token))
    flash("Transaction signalée. Le commerçant doit vérifier la transaction sur le réseau avant de confirmer le paiement.")
    return redirect(url_for("invoice", token=token))

@app.post("/admin/invoice/<int:invoice_id>/status")
@login_required
def update_status(invoice_id):
    status = request.form.get("status")
    if status not in ("pending", "paid", "cancelled"):
        abort(400)
    with db() as c:
        c.execute("UPDATE invoices SET status=? WHERE id=?", (status, invoice_id))
    flash("Statut mis à jour. Vérifie toujours la transaction sur le bon explorateur avant de marquer payé.")
    return redirect(url_for("dashboard"))

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", message="Page ou facture introuvable."), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
