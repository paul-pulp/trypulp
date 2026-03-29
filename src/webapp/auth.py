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

    # In development, just print the link
    if not smtp_user or not smtp_pass:
        print(f"\n  [DEV MODE] Magic link for {email}:")
        print(f"  {magic_link}\n")
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
        with smtplib.SMTP(current_app.config["SMTP_HOST"],
                          current_app.config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"  Email send failed: {e}")
        return False
