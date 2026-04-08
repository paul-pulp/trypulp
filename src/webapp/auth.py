"""
Magic link authentication — no passwords.
"""

import os
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from flask import current_app
from itsdangerous import URLSafeSerializer, BadSignature


UNSUB_SALT = "pulpiq-unsubscribe-v1"


def generate_magic_link(user_id):
    """Create a token and return the full magic link URL."""
    from .models import create_token

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    create_token(user_id, token, expires_at)

    app_url = current_app.config["APP_URL"].rstrip("/")
    return f"{app_url}/verify?token={token}"


def generate_unsubscribe_link(user_id):
    """Build a signed unsubscribe URL (no DB token needed)."""
    serializer = URLSafeSerializer(current_app.config["SECRET_KEY"], salt=UNSUB_SALT)
    token = serializer.dumps(int(user_id))
    app_url = current_app.config["APP_URL"].rstrip("/")
    return f"{app_url}/unsubscribe?token={token}"


def verify_unsubscribe_token(token):
    """Return user_id from a signed unsubscribe token, or None if invalid."""
    serializer = URLSafeSerializer(current_app.config["SECRET_KEY"], salt=UNSUB_SALT)
    try:
        return int(serializer.loads(token))
    except (BadSignature, ValueError, TypeError):
        return None


def unsubscribe_footer(user_id):
    """Plain-text footer for marketing emails (CASL compliance)."""
    link = generate_unsubscribe_link(user_id)
    return (
        f"\n\n---\n"
        f"PulpIQ — hello@trypulp.co\n"
        f"Don't want these emails? Unsubscribe: {link}"
    )


def send_magic_link_email(email, magic_link, is_new_user=False, cafe_name="", user_id=None):
    """Send the magic link via SMTP. Attaches onboarding PDF for new users."""
    smtp_user = current_app.config["SMTP_USER"]
    smtp_pass = current_app.config["SMTP_PASS"]

    # Always log the magic link (visible in Render logs)
    print(f"[AUTH] Magic link for {email}: {magic_link}", flush=True)
    print(f"[AUTH] New user: {is_new_user}", flush=True)

    # In development, skip email
    if not smtp_user or not smtp_pass:
        print(f"[AUTH] No SMTP credentials — skipping email send", flush=True)
        return True

    # Build the email
    if is_new_user:
        subject = "Welcome to PulpIQ — Here's How to Get Started"
        body = (
            f"Hi!\n\n"
            f"Welcome to PulpIQ. We're excited to help you see what's working "
            f"and what's wasting at {cafe_name or 'your cafe'}.\n\n"
            f"Click this link to sign in:\n\n"
            f"{magic_link}\n\n"
            f"We've attached a quick guide showing how to export your sales data "
            f"from Square, Toast, Clover, or any POS system. The whole process "
            f"takes about 2 minutes.\n\n"
            f"Once you're logged in, just drag in your CSV and you'll see your "
            f"first insights instantly.\n\n"
            f"Questions? Just reply to this email.\n\n"
            f"— The PulpIQ Team\n"
            f"hello@trypulp.co"
        )
        if user_id is not None:
            body += unsubscribe_footer(user_id)
    else:
        subject = "Your PulpIQ Sign-In Link"
        body = (
            f"Hi!\n\n"
            f"Click this link to sign in to PulpIQ:\n\n"
            f"{magic_link}\n\n"
            f"This link expires in 15 minutes.\n\n"
            f"— PulpIQ"
        )

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"PulpIQ <{smtp_user}>"
    msg["To"] = email
    msg.attach(MIMEText(body, "plain"))

    # Attach onboarding PDF for new users
    pdf_path = None
    if is_new_user:
        try:
            from .onboarding_pdf import generate
            pdf_path = generate(cafe_name)
            with open(pdf_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment; filename=PulpIQ-Getting-Started.pdf",
                )
                msg.attach(part)
            print(f"[AUTH] Onboarding PDF attached", flush=True)
        except Exception as e:
            print(f"[AUTH] PDF generation failed (sending without it): {e}", flush=True)

    try:
        print(f"[AUTH] Sending to {email}...", flush=True)
        with smtplib.SMTP(current_app.config["SMTP_HOST"],
                          current_app.config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[AUTH] Email sent successfully", flush=True)
        return True
    except Exception as e:
        print(f"[AUTH] Email send FAILED: {e}", flush=True)
        return False
    finally:
        # Clean up temp PDF
        if pdf_path:
            try:
                os.unlink(pdf_path)
            except OSError:
                pass
