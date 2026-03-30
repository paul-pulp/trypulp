"""
Authentication views — login, verify magic link, logout.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from ..models import get_user_by_email, create_user, verify_token, get_user_by_id
from ..auth import generate_magic_link, send_magic_link_email

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

    # Generate and send magic link (with onboarding PDF for new users)
    link = generate_magic_link(user["id"])
    send_magic_link_email(email, link, is_new_user=is_new, cafe_name=user["cafe_name"])

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
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
