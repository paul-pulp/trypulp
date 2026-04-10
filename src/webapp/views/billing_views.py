"""
Billing views — Stripe Checkout for subscriptions.
"""

import stripe
from flask import Blueprint, redirect, url_for, session, request, current_app, flash, jsonify

from ..models import get_user_by_id, update_user_subscription

billing_bp = Blueprint("billing", __name__)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@billing_bp.route("/upgrade")
@login_required
def paywall():
    """Show the upgrade page when free/trial uploads are exhausted."""
    from flask import render_template
    user = get_user_by_id(session["user_id"])
    return render_template("paywall.html", user=user)


@billing_bp.route("/subscribe")
@login_required
def subscribe():
    """Redirect to Stripe Checkout to start a subscription."""
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    if not stripe.api_key:
        flash("Payments are not configured yet.", "error")
        return redirect(url_for("dashboard.dashboard"))

    user = get_user_by_id(session["user_id"])
    app_url = current_app.config["APP_URL"].rstrip("/")

    # Create or reuse Stripe customer
    customer_id = user["stripe_customer_id"] if "stripe_customer_id" in user.keys() else None
    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            name=user["cafe_name"],
            metadata={"pulpiq_user_id": str(user["id"])},
        )
        customer_id = customer.id
        update_user_subscription(user["id"], stripe_customer_id=customer_id)

    # Create Checkout Session
    try:
        checkout = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": current_app.config["STRIPE_PRICE_ID"],
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{app_url}/billing/cancel",
            metadata={"pulpiq_user_id": str(user["id"])},
        )
        return redirect(checkout.url, code=303)
    except Exception as e:
        print(f"[BILLING] Stripe error: {e}", flush=True)
        flash("Something went wrong with payments. Please try again.", "error")
        return redirect(url_for("dashboard.dashboard"))


@billing_bp.route("/billing/success")
@login_required
def billing_success():
    """Handle successful Stripe Checkout — activate subscription."""
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
    session_id = request.args.get("session_id")

    if session_id:
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            subscription_id = checkout.subscription
            user_id = session["user_id"]

            update_user_subscription(
                user_id,
                stripe_subscription_id=subscription_id,
                subscription_status="active",
            )

            print(f"[BILLING] User {user_id} subscribed: {subscription_id}", flush=True)
            flash("You're subscribed! Upload your data anytime.", "success")

            # Send welcome email
            user = get_user_by_id(user_id)
            _send_welcome_email(user)

        except Exception as e:
            print(f"[BILLING] Success handler error: {e}", flush=True)
            flash("Payment received! Your account is being activated.", "success")

    return redirect(url_for("dashboard.dashboard"))


def _send_welcome_email(user):
    """Send a congratulations email to new Pro subscribers."""
    import smtplib
    from email.mime.text import MIMEText

    smtp_user = current_app.config.get("SMTP_USER", "")
    smtp_pass = current_app.config.get("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        return

    cafe = user["cafe_name"] if user else "there"
    email = user["email"] if user else ""

    body = (
        f"Hey {cafe} team!\n\n"
        f"Welcome to PulpIQ Pro. You're all set.\n\n"
        f"Here's what you can do now:\n\n"
        f"  1. Upload your sales data every week\n"
        f"  2. See how your revenue and waste are trending\n"
        f"  3. Get specific action items each week based on your numbers\n"
        f"  4. Track your cumulative savings over time\n\n"
        f"Your next step: head to your dashboard and upload this week's data.\n\n"
        f"  {current_app.config['APP_URL']}/dashboard\n\n"
        f"If you ever need help or have questions, just reply to this email.\n\n"
        f"Thanks for trusting us with your data.\n\n"
        f"— The PulpIQ Team\n"
        f"hello@trypulp.co"
    )

    from ..auth import plain_to_html
    html_body = plain_to_html(body, user_id=user["id"])

    msg = MIMEText(html_body, "html")
    msg["Subject"] = f"Welcome to PulpIQ Pro, {cafe}!"
    msg["From"] = f"PulpIQ <{smtp_user}>"
    msg["To"] = email

    try:
        with smtplib.SMTP(current_app.config["SMTP_HOST"],
                          current_app.config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[BILLING] Welcome email sent to {email}", flush=True)
    except Exception as e:
        print(f"[BILLING] Welcome email failed: {e}", flush=True)


@billing_bp.route("/billing/cancel")
@login_required
def billing_cancel():
    """Handle cancelled Stripe Checkout."""
    flash("No worries — you can subscribe anytime.", "info")
    return redirect(url_for("dashboard.dashboard"))


@billing_bp.route("/billing/manage")
@login_required
def billing_manage():
    """Redirect to Stripe Customer Portal for subscription management."""
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

    user = get_user_by_id(session["user_id"])
    customer_id = user["stripe_customer_id"] if "stripe_customer_id" in user.keys() else None

    if not customer_id:
        flash("No active subscription found.", "error")
        return redirect(url_for("dashboard.dashboard"))

    app_url = current_app.config["APP_URL"].rstrip("/")

    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{app_url}/dashboard",
        )
        return redirect(portal.url, code=303)
    except Exception as e:
        print(f"[BILLING] Portal error: {e}", flush=True)
        flash("Could not open billing portal. Please try again.", "error")
        return redirect(url_for("dashboard.dashboard"))
