"""
Dashboard and report views.
"""

import json
from flask import Blueprint, render_template, session, redirect, url_for, abort

from ..models import (
    get_user_by_id, get_snapshots_for_user, get_snapshot_by_id, get_latest_snapshot,
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

    return render_template("report.html",
                           user=user,
                           snapshot=snapshot,
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
