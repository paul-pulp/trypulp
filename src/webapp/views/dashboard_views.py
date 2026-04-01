"""
Dashboard and report views.
"""

import json
from flask import Blueprint, render_template, request, session, redirect, url_for, abort, flash

from ..models import (
    get_user_by_id, get_snapshots_for_user, get_snapshot_by_id, get_latest_snapshot,
    insert_feedback, delete_latest_snapshot, count_snapshots, update_user_costs,
    save_user_orders, get_user_orders,
)

dashboard_bp = Blueprint("dashboard", __name__)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    snapshots = get_snapshots_for_user(user_id)

    # Parse the latest snapshot for the summary card
    latest = None
    if snapshots:
        latest = dict(snapshots[0])
        if latest.get("comparison_results"):
            latest["comparison"] = json.loads(latest["comparison_results"])

    return render_template("dashboard.html",
                           user=user,
                           snapshots=snapshots,
                           latest=latest)


@dashboard_bp.route("/report/<int:snapshot_id>")
@login_required
def report(snapshot_id):
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    snapshot = get_snapshot_by_id(snapshot_id, user_id)

    if snapshot is None:
        abort(404)

    customer = json.loads(snapshot["customer_results"])
    waste = json.loads(snapshot["waste_results"])
    comparison = None
    if snapshot["comparison_results"]:
        comparison = json.loads(snapshot["comparison_results"])

    # Check if this is the most recent snapshot (for delete button)
    latest = get_latest_snapshot(user_id)
    is_latest = latest is not None and latest["id"] == snapshot_id

    # Get user's actual order quantities (if they've entered them)
    user_orders = get_user_orders(user_id)

    return render_template("report.html",
                           user=user,
                           snapshot=snapshot,
                           is_latest=is_latest,
                           user_orders=user_orders,
                           customer=customer,
                           waste=waste,
                           comparison=comparison)


@dashboard_bp.route("/compare/<int:snapshot_id>")
@login_required
def compare(snapshot_id):
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    snapshot = get_snapshot_by_id(snapshot_id, user_id)

    if snapshot is None or not snapshot["comparison_results"]:
        abort(404)

    comparison = json.loads(snapshot["comparison_results"])
    customer = json.loads(snapshot["customer_results"])
    waste = json.loads(snapshot["waste_results"])

    return render_template("comparison.html",
                           user=user,
                           snapshot=snapshot,
                           comparison=comparison,
                           customer=customer,
                           waste=waste)


@dashboard_bp.route("/costs", methods=["GET", "POST"])
@login_required
def costs():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)

    if request.method == "GET":
        return render_template("costs.html", user=user)

    # Save costs
    ingredient_pct = request.form.get("ingredient_pct", "").strip()

    update_user_costs(
        user_id,
        ingredient_pct=int(ingredient_pct) if ingredient_pct else None,
    )

    flash("Your costs are saved! Future reports will use your actual numbers.", "success")
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/report/<int:snapshot_id>/orders", methods=["POST"])
@login_required
def save_orders(snapshot_id):
    user_id = session["user_id"]

    # Collect all order_xxx fields from the form
    orders = {}
    for key, val in request.form.items():
        if key.startswith("order_") and val.strip():
            item_name = key[6:]  # strip "order_" prefix
            try:
                qty = int(float(val))
                if qty > 0:
                    orders[item_name] = qty
            except (ValueError, TypeError):
                pass

    if orders:
        save_user_orders(user_id, orders)
        flash(f"Saved your actual orders for {len(orders)} items. Waste numbers updated.", "success")
    else:
        flash("No changes saved.", "info")

    return redirect(url_for("dashboard.report", snapshot_id=snapshot_id))


@dashboard_bp.route("/report/<int:snapshot_id>/delete", methods=["POST"])
@login_required
def delete_report(snapshot_id):
    user_id = session["user_id"]

    # Only allow deleting the most recent snapshot
    latest = get_latest_snapshot(user_id)
    if latest is None or latest["id"] != snapshot_id:
        flash("You can only delete your most recent upload.", "error")
        return redirect(url_for("dashboard.dashboard"))

    delete_latest_snapshot(user_id)
    print(f"[DELETE] User {user_id} deleted snapshot {snapshot_id}", flush=True)
    flash("Upload deleted. You can upload a new file.", "success")
    return redirect(url_for("dashboard.dashboard"))


@dashboard_bp.route("/feedback", methods=["POST"])
@login_required
def feedback():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    feedback_type = request.form.get("feedback_type", "feedback")
    message = request.form.get("message", "").strip()

    if message:
        insert_feedback(user_id, feedback_type, message)
        print(f"[FEEDBACK] {feedback_type} from user {user_id}: {message[:100]}", flush=True)

        # Email feedback to hello@trypulp.co
        _email_feedback(user, feedback_type, message)

        flash("Thanks for your feedback!", "success")
    else:
        flash("Please enter a message.", "error")

    return redirect(url_for("dashboard.dashboard"))


def _email_feedback(user, feedback_type, message):
    """Send feedback notification to hello@trypulp.co."""
    import smtplib
    from email.mime.text import MIMEText
    from flask import current_app

    smtp_user = current_app.config.get("SMTP_USER", "")
    smtp_pass = current_app.config.get("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        return

    cafe = user["cafe_name"] if user else "Unknown"
    email = user["email"] if user else "Unknown"

    type_label = feedback_type.replace("_", " ").title()

    body = (
        f"New {type_label} from {cafe} ({email}):\n\n"
        f"{message}\n\n"
        f"---\n"
        f"View all feedback: {current_app.config['APP_URL']}/admin/feedback"
    )

    msg = MIMEText(body, "plain")
    msg["Subject"] = f"[PulpIQ {type_label}] {cafe}"
    msg["From"] = f"PulpIQ <{smtp_user}>"
    msg["To"] = "hello@trypulp.co"

    try:
        with smtplib.SMTP(current_app.config["SMTP_HOST"],
                          current_app.config["SMTP_PORT"]) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"[FEEDBACK] Email sent to hello@trypulp.co", flush=True)
    except Exception as e:
        print(f"[FEEDBACK] Email failed: {e}", flush=True)
