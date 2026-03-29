"""
Magic link authentication — no passwords.
"""

import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from flask import current_app


def generate_magic_link(user_id):
    """Create a token and return the full magic link URL."""
    from .models import create_token

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    create_token(user_id, token, expires_at)

    app_url = current_app.config["APP_URL"].rstrip("/")
    return f"{app_url}/verify?token={token}"


def send_magic_link_email(email, magic_link):
    """Send the magic link via SMTP."""
    smtp_user = current_app.config["SMTP_USER"]
    smtp_pass = current_app.config["SMTP_PASS"]

    # Always log the magic link (visible in Render logs)
    print(f"[AUTH] Magic link for {email}: {magic_link}", flush=True)
    print(f"[AUTH] SMTP_USER configured: {'yes' if smtp_user else 'no'}", flush=True)
    print(f"[AUTH] SMTP_PASS configured: {'yes' if smtp_pass else 'no'}", flush=True)

    # In development, skip email
    if not smtp_user or not smtp_pass:
        print(f"[AUTH] No SMTP credentials — skipping email send", flush=True)
        return True

    msg = MIMEText(
        f"Hi!\n\n"
        f"Click this link to sign in to PulpIQ:\n\n"
        f"{magic_link}\n\n"
        f"This link expires in 15 minutes.\n\n"
        f"— PulpIQ",
        "plain",
    )
    msg["Subject"] = "Your PulpIQ Sign-In Link"
    msg["From"] = smtp_user
    msg["To"] = email

    try:
        print(f"[AUTH] Connecting to {current_app.config['SMTP_HOST']}:{current_app.config['SMTP_PORT']}...", flush=True)
        with smtplib.SMTP(current_app.config["SMTP_HOST"],
                          current_app.config["SMTP_PORT"]) as server:
            server.starttls()
            print(f"[AUTH] Logging in as {smtp_user}...", flush=True)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[AUTH] Email sent successfully to {email}", flush=True)
        return True
    except Exception as e:
        print(f"[AUTH] Email send FAILED: {e}", flush=True)
        # Still log the link so user can find it in logs
        return False
