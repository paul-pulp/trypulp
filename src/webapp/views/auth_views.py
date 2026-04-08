"""
Authentication views — login, verify magic link, logout.
"""

import smtplib
from email.mime.text import MIMEText
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app

from ..models import (
    get_user_by_email, create_user, verify_token, get_user_by_id,
    count_snapshots, set_user_unsubscribed,
)
from ..auth import generate_magic_link, send_magic_link_email, verify_unsubscribe_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    cafe_name = request.form.get("cafe_name", "").strip()

    if not email:
        flash("Please enter your email.", "error")
        return render_template("login.html")

    # Find or create user
    user = get_user_by_email(email)
    is_new = user is None
    if is_new:
        if not cafe_name:
            # New user needs a cafe name — show the full form
            return render_template("login.html", email=email, needs_cafe_name=True)
        user = create_user(email, cafe_name)
        _notify_new_signup(email, cafe_name)

    # Generate and send magic link (with onboarding PDF for new users)
    link = generate_magic_link(user["id"])
    send_magic_link_email(email, link, is_new_user=is_new, cafe_name=user["cafe_name"], user_id=user["id"])

    return render_template("check_email.html", email=email)


@auth_bp.route("/verify")
def verify():
    token = request.args.get("token", "")
    user_id = verify_token(token)

    if user_id is None:
        flash("Invalid or expired link. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    session.clear()
    session["user_id"] = user_id

    # New users go straight to upload, returning users go to dashboard
    if count_snapshots(user_id) == 0:
        return redirect(url_for("upload.upload"))
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/unsubscribe")
def unsubscribe():
    """One-click unsubscribe from PulpIQ marketing emails (CASL compliance)."""
    token = request.args.get("token", "")
    user_id = verify_unsubscribe_token(token)

    if user_id is None:
        return render_template("unsubscribe.html", success=False), 400

    user = get_user_by_id(user_id)
    if user is None:
        return render_template("unsubscribe.html", success=False), 404

    set_user_unsubscribed(user_id)
    print(f"[UNSUB] User {user_id} ({user['email']}) unsubscribed", flush=True)
    return render_template("unsubscribe.html", success=True, email=user["email"])


def _notify_new_signup(email, cafe_name):
    """Email hello@trypulp.co when a new user signs up."""
    smtp_user = current_app.config.get("SMTP_USER", "")
    smtp_pass = current_app.config.get("SMTP_PASS", "")
    if not smtp_user or not smtp_pass:
        return

    body = f"New signup!\n\nCafe: {cafe_name}\nEmail: {email}\n\nView all users: {current_app.config['APP_URL']}/admin/users"

    msg = MIMEText(body, "plain")
    msg["Subject"] = f"New PulpIQ signup: {cafe_name}"
    msg["From"] = f"PulpIQ <{smtp_user}>"
    msg["To"] = "hello@trypulp.co"

    try:
        with smtplib.SMTP(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[AUTH] Signup notification sent for {cafe_name}", flush=True)
    except Exception as e:
        print(f"[AUTH] Signup notification failed: {e}", flush=True)
