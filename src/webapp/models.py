"""
Database models — plain SQLite, no ORM.
"""

import sqlite3
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    db = sqlite3.connect(app.config["DATABASE"])
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            cafe_name TEXT NOT NULL,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            subscription_status TEXT DEFAULT 'free',
            trial_uploads_remaining INTEGER DEFAULT 2,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            week_number INTEGER NOT NULL,
            csv_filename TEXT NOT NULL,
            date_start TEXT,
            date_end TEXT,
            avg_daily_revenue REAL,
            avg_ticket_size REAL,
            avg_daily_transactions REAL,
            total_revenue REAL,
            waste_units_daily REAL,
            waste_monthly_cost REAL,
            waste_savings_monthly REAL,
            customer_results TEXT NOT NULL,
            waste_results TEXT NOT NULL,
            comparison_results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, week_number)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            feedback_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            item_name TEXT NOT NULL,
            daily_order INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, item_name)
        );
    """)
    # Migrations: add columns if they don't exist (safe to run repeatedly)
    try:
        db.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'free'")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN trial_uploads_remaining INTEGER DEFAULT 2")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN cost_milk_per_gallon REAL")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN cost_pastry_avg REAL")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN cost_ingredient_pct INTEGER")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN cost_hourly_wage REAL")
    except Exception:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN costs_updated INTEGER DEFAULT 0")
    except Exception:
        pass
    db.commit()

    db.close()
    app.teardown_appcontext(close_db)


# ── User operations ────────────────────────────────────────────────────

def get_all_users_with_stats():
    """Get all users with their upload count and latest activity."""
    return get_db().execute("""
        SELECT
            u.id, u.email, u.cafe_name, u.created_at,
            u.subscription_status, u.trial_uploads_remaining,
            COUNT(s.id) as upload_count,
            MAX(s.created_at) as last_upload,
            MAX(s.avg_daily_revenue) as latest_revenue,
            MAX(s.waste_savings_monthly) as best_savings,
            MAX(s.waste_monthly_cost) as latest_waste_cost
        FROM users u
        LEFT JOIN snapshots s ON u.id = s.user_id
        GROUP BY u.id
        ORDER BY MAX(s.waste_savings_monthly) DESC NULLS LAST
    """).fetchall()


def update_user_subscription(user_id, stripe_customer_id=None, stripe_subscription_id=None,
                             subscription_status=None, trial_uploads_remaining=None):
    """Update subscription fields on a user."""
    db = get_db()
    fields = []
    values = []
    if stripe_customer_id is not None:
        fields.append("stripe_customer_id = ?")
        values.append(stripe_customer_id)
    if stripe_subscription_id is not None:
        fields.append("stripe_subscription_id = ?")
        values.append(stripe_subscription_id)
    if subscription_status is not None:
        fields.append("subscription_status = ?")
        values.append(subscription_status)
    if trial_uploads_remaining is not None:
        fields.append("trial_uploads_remaining = ?")
        values.append(trial_uploads_remaining)
    if fields:
        values.append(user_id)
        db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()


def can_upload(user):
    """Check if a user can upload (free baseline, trial, or active subscription)."""
    snapshot_count = count_snapshots(user["id"])

    # First upload (baseline) is always free
    if snapshot_count == 0:
        return True

    # Active subscriber
    status = user["subscription_status"] if "subscription_status" in user.keys() else "free"
    if status == "active":
        return True

    # Trial uploads remaining
    trial_remaining = user["trial_uploads_remaining"] if "trial_uploads_remaining" in user.keys() else 2
    if trial_remaining is not None and trial_remaining > 0:
        return True

    return False


def use_trial_upload(user_id):
    """Decrement trial uploads remaining."""
    db = get_db()
    db.execute(
        "UPDATE users SET trial_uploads_remaining = MAX(0, COALESCE(trial_uploads_remaining, 2) - 1) WHERE id = ?",
        (user_id,),
    )
    db.commit()


def update_user_costs(user_id, ingredient_pct=None):
    """Update the cafe's ingredient cost percentage."""
    db = get_db()
    fields = ["costs_updated = 1"]
    values = []
    if ingredient_pct is not None:
        fields.append("cost_ingredient_pct = ?")
        values.append(ingredient_pct)
    values.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
    db.commit()


def get_user_cost_overrides(user):
    """Build a cost_overrides dict from the user's ingredient cost percentage."""
    overrides = {}
    ingredient_pct = user["cost_ingredient_pct"] if "cost_ingredient_pct" in user.keys() else None
    if ingredient_pct and ingredient_pct > 0:
        overrides["perishable_cogs_ratio"] = ingredient_pct / 100.0  # 30 → 0.30
    return overrides if overrides else None


def get_user_by_email(email):
    return get_db().execute(
        "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
    ).fetchone()


def get_user_by_id(user_id):
    return get_db().execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def create_user(email, cafe_name):
    db = get_db()
    db.execute(
        "INSERT INTO users (email, cafe_name) VALUES (?, ?)",
        (email.lower().strip(), cafe_name.strip()),
    )
    db.commit()
    return get_user_by_email(email)


# ── Token operations ───────────────────────────────────────────────────

def create_token(user_id, token, expires_at):
    db = get_db()
    db.execute(
        "INSERT INTO auth_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at),
    )
    db.commit()


def verify_token(token):
    """Verify and consume a magic link token. Returns user_id or None."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM auth_tokens WHERE token = ? AND used = 0 AND expires_at > datetime('now')",
        (token,),
    ).fetchone()
    if row is None:
        return None
    db.execute("UPDATE auth_tokens SET used = 1 WHERE id = ?", (row["id"],))
    db.commit()
    return row["user_id"]


# ── Snapshot operations ────────────────────────────────────────────────

def get_snapshots_for_user(user_id):
    return get_db().execute(
        "SELECT * FROM snapshots WHERE user_id = ? ORDER BY week_number DESC",
        (user_id,),
    ).fetchall()


def get_snapshot_by_id(snapshot_id, user_id):
    return get_db().execute(
        "SELECT * FROM snapshots WHERE id = ? AND user_id = ?",
        (snapshot_id, user_id),
    ).fetchone()


def get_latest_snapshot(user_id):
    return get_db().execute(
        "SELECT * FROM snapshots WHERE user_id = ? ORDER BY week_number DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def get_baseline_snapshot(user_id):
    return get_db().execute(
        "SELECT * FROM snapshots WHERE user_id = ? AND week_number = 0",
        (user_id,),
    ).fetchone()


def delete_latest_snapshot(user_id):
    """Delete the most recent snapshot for a user. Returns True if deleted."""
    db = get_db()
    latest = db.execute(
        "SELECT id, week_number FROM snapshots WHERE user_id = ? ORDER BY week_number DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if latest is None:
        return False
    db.execute("DELETE FROM snapshots WHERE id = ?", (latest["id"],))
    db.commit()
    return True


def count_snapshots(user_id):
    row = get_db().execute(
        "SELECT COUNT(*) as cnt FROM snapshots WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["cnt"]


def insert_snapshot(user_id, week_number, csv_filename, date_start, date_end,
                    avg_daily_revenue, avg_ticket_size, avg_daily_transactions,
                    total_revenue, waste_units_daily, waste_monthly_cost,
                    waste_savings_monthly, customer_results_json, waste_results_json,
                    comparison_results_json=None):
    db = get_db()
    cursor = db.execute(
        """INSERT INTO snapshots (
            user_id, week_number, csv_filename, date_start, date_end,
            avg_daily_revenue, avg_ticket_size, avg_daily_transactions,
            total_revenue, waste_units_daily, waste_monthly_cost,
            waste_savings_monthly, customer_results, waste_results,
            comparison_results
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, week_number, csv_filename, date_start, date_end,
         avg_daily_revenue, avg_ticket_size, avg_daily_transactions,
         total_revenue, waste_units_daily, waste_monthly_cost,
         waste_savings_monthly, customer_results_json, waste_results_json,
         comparison_results_json),
    )
    db.commit()
    return cursor.lastrowid


# ── Feedback operations ────────────────────────────────────────────────

def insert_feedback(user_id, feedback_type, message):
    db = get_db()
    db.execute(
        "INSERT INTO feedback (user_id, feedback_type, message) VALUES (?, ?, ?)",
        (user_id, feedback_type, message.strip()),
    )
    db.commit()


def get_all_feedback():
    """Get all feedback with user info, newest first."""
    return get_db().execute("""
        SELECT f.id, f.feedback_type, f.message, f.created_at,
               u.cafe_name, u.email
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """).fetchall()


# ── User order quantities ──────────────────────────────────────────────

def save_user_orders(user_id, orders_dict):
    """Save actual order quantities. orders_dict = {item_name: daily_order}."""
    db = get_db()
    for item_name, qty in orders_dict.items():
        if qty and int(qty) > 0:
            db.execute(
                """INSERT INTO user_orders (user_id, item_name, daily_order)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, item_name) DO UPDATE SET
                   daily_order = ?, updated_at = CURRENT_TIMESTAMP""",
                (user_id, item_name, int(qty), int(qty)),
            )
    db.commit()


def get_user_orders(user_id):
    """Get saved order quantities as {item_name: daily_order}."""
    rows = get_db().execute(
        "SELECT item_name, daily_order FROM user_orders WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {row["item_name"]: row["daily_order"] for row in rows}
