"""
Weekly upload reminders — emails users who haven't uploaded in 7+ days.
Runs daily alongside the backup thread.
"""

import smtplib
from email.mime.text import MIMEText
from flask import current_app


def send_weekly_reminders(app):
    """Check for users who uploaded 7+ days ago but haven't uploaded since. Email them."""
    with app.app_context():
        from .models import get_db

        smtp_user = app.config.get("SMTP_USER", "")
        smtp_pass = app.config.get("SMTP_PASS", "")
        app_url = app.config.get("APP_URL", "https://trypulp.co")

        if not smtp_user or not smtp_pass:
            print("[REMINDERS] No SMTP credentials — skipping", flush=True)
            return

        db = get_db()

        # Find users whose latest upload was 7-8 days ago (so we only remind once)
        users_to_remind = db.execute("""
            SELECT u.id, u.email, u.cafe_name, MAX(s.created_at) as last_upload
            FROM users u
            JOIN snapshots s ON u.id = s.user_id
            GROUP BY u.id
            HAVING last_upload IS NOT NULL
              AND last_upload < datetime('now', '-7 days')
              AND last_upload > datetime('now', '-8 days')
        """).fetchall()

        if not users_to_remind:
            print("[REMINDERS] No users need reminding today", flush=True)
            return

        print(f"[REMINDERS] Sending reminders to {len(users_to_remind)} users", flush=True)

        for user in users_to_remind:
            _send_reminder(user, smtp_user, smtp_pass, app_url, app.config)


def _send_reminder(user, smtp_user, smtp_pass, app_url, config):
    """Send a single reminder email."""
    cafe = user["cafe_name"]
    email = user["email"]

    body = (
        f"Hey {cafe} team!\n\n"
        f"It's been a week since your last upload. Got new sales data?\n\n"
        f"Upload this week's numbers and see how things are trending:\n\n"
        f"  {app_url}/upload\n\n"
        f"It takes about 2 minutes — export from your POS, drag it in, "
        f"and see your week-over-week comparison instantly.\n\n"
        f"— The PulpIQ Team\n"
        f"hello@trypulp.co\n\n"
        f"Don't want these reminders? Just reply and let us know."
    )

    msg = MIMEText(body, "plain")
    msg["Subject"] = f"{cafe} — time to check this week's numbers"
    msg["From"] = f"PulpIQ <{smtp_user}>"
    msg["To"] = email

    try:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[REMINDERS] Sent to {email}", flush=True)
    except Exception as e:
        print(f"[REMINDERS] Failed for {email}: {e}", flush=True)
