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
    """)
    db.close()
    app.teardown_appcontext(close_db)


# ── User operations ────────────────────────────────────────────────────

def get_all_users_with_stats():
    """Get all users with their upload count and latest activity."""
    return get_db().execute("""
        SELECT
            u.id, u.email, u.cafe_name, u.created_at,
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
