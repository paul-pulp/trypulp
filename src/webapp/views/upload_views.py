"""
CSV upload and analysis views.
"""

import os
import json
import tempfile
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from ..models import count_snapshots, get_latest_snapshot, insert_snapshot, get_user_by_id
from ..analysis_runner import run_analysis, serialize_results

upload_bp = Blueprint("upload", __name__)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@upload_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        user = get_user_by_id(session["user_id"])
        week_num = count_snapshots(session["user_id"])
        label = "baseline" if week_num == 0 else f"week {week_num}"
        return render_template("upload.html", cafe_name=user["cafe_name"],
                               upload_label=label)

    # Handle file upload
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("Please select a CSV file.", "error")
        return redirect(url_for("upload.upload"))

    if not file.filename.lower().endswith(".csv"):
        flash("Please upload a .csv file.", "error")
        return redirect(url_for("upload.upload"))

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    try:
        file.save(tmp.name)
        tmp.close()

        print(f"[UPLOAD] Processing {file.filename} ({os.path.getsize(tmp.name) / 1024:.1f} KB)", flush=True)

        # Run analysis
        result = run_analysis(tmp.name)

        if result["errors"]:
            for err in result["errors"]:
                flash(err, "error")
            return redirect(url_for("upload.upload"))

        # Show warnings but continue
        for warn in result["warnings"]:
            flash(warn, "warning")

        # Determine week number
        user_id = session["user_id"]
        week_number = count_snapshots(user_id)

        # Compare with previous if not baseline
        comparison_json = None
        if week_number > 0:
            prev = get_latest_snapshot(user_id)
            if prev:
                comparison = _build_comparison(result, prev)
                comparison_json = json.dumps(comparison)

        # Store snapshot
        customer = result["customer"]
        waste = result["waste"]
        summary = customer["summary"]
        waste_proj = waste.get("waste_projection", {})

        snapshot_id = insert_snapshot(
            user_id=user_id,
            week_number=week_number,
            csv_filename=file.filename,
            date_start=customer["data_range"]["start"],
            date_end=customer["data_range"]["end"],
            avg_daily_revenue=summary["avg_daily_revenue"],
            avg_ticket_size=summary["avg_ticket_size"],
            avg_daily_transactions=summary["avg_daily_transactions"],
            total_revenue=summary["total_revenue"],
            waste_units_daily=waste_proj.get("total_daily_waste_units", 0),
            waste_monthly_cost=waste_proj.get("total_monthly_waste_cost", 0),
            waste_savings_monthly=waste["savings"].get("total_savings_monthly", 0),
            customer_results_json=json.dumps(serialize_results(customer)),
            waste_results_json=json.dumps(serialize_results(waste)),
            comparison_results_json=comparison_json,
        )

        return redirect(url_for("dashboard.report", snapshot_id=snapshot_id))

    except Exception as e:
        import traceback
        print(f"[UPLOAD] ERROR: {e}", flush=True)
        traceback.print_exc()
        flash(f"Analysis failed: {e}", "error")
        return redirect(url_for("upload.upload"))

    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _build_comparison(current_result, prev_snapshot):
    """Build a simple comparison dict between current results and previous snapshot."""
    curr_summary = current_result["customer"]["summary"]
    curr_waste = current_result["waste"].get("waste_projection", {})

    return {
        "revenue": {
            "current": curr_summary["avg_daily_revenue"],
            "previous": prev_snapshot["avg_daily_revenue"],
            "change": round(curr_summary["avg_daily_revenue"] - prev_snapshot["avg_daily_revenue"], 2),
        },
        "ticket": {
            "current": curr_summary["avg_ticket_size"],
            "previous": prev_snapshot["avg_ticket_size"],
            "change": round(curr_summary["avg_ticket_size"] - prev_snapshot["avg_ticket_size"], 2),
        },
        "transactions": {
            "current": curr_summary["avg_daily_transactions"],
            "previous": prev_snapshot["avg_daily_transactions"],
            "change": round(curr_summary["avg_daily_transactions"] - prev_snapshot["avg_daily_transactions"], 1),
        },
        "waste_units": {
            "current": curr_waste.get("total_daily_waste_units", 0),
            "previous": prev_snapshot["waste_units_daily"] or 0,
            "change": round(
                curr_waste.get("total_daily_waste_units", 0) - (prev_snapshot["waste_units_daily"] or 0), 1
            ),
        },
        "waste_cost": {
            "current": curr_waste.get("total_monthly_waste_cost", 0),
            "previous": prev_snapshot["waste_monthly_cost"] or 0,
            "change": round(
                curr_waste.get("total_monthly_waste_cost", 0) - (prev_snapshot["waste_monthly_cost"] or 0), 2
            ),
        },
    }
