"""
CSV upload and analysis views.
"""

import os
import json
import tempfile
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from ..models import count_snapshots, get_latest_snapshot, get_baseline_snapshot, get_snapshots_for_user, insert_snapshot, get_user_by_id
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

        # Compare with previous + baseline if not baseline
        comparison_json = None
        if week_number > 0:
            prev = get_latest_snapshot(user_id)
            baseline = get_baseline_snapshot(user_id)
            all_snaps = get_snapshots_for_user(user_id)
            if prev:
                comparison = _build_comparison(result, prev, baseline, all_snaps)
                comparison_json = json.dumps(comparison)

        # Store snapshot
        customer = result["customer"]
        waste = result["waste"]
        summary = customer.get("summary") or {}
        waste_proj = waste.get("waste_projection") or {}
        waste_savings = waste.get("savings") or {}

        snapshot_id = insert_snapshot(
            user_id=user_id,
            week_number=week_number,
            csv_filename=file.filename,
            date_start=(customer.get("data_range") or {}).get("start", ""),
            date_end=(customer.get("data_range") or {}).get("end", ""),
            avg_daily_revenue=summary.get("avg_daily_revenue", 0),
            avg_ticket_size=summary.get("avg_ticket_size", 0),
            avg_daily_transactions=summary.get("avg_daily_transactions", 0),
            total_revenue=summary.get("total_revenue", 0),
            waste_units_daily=waste_proj.get("total_daily_waste_units", 0),
            waste_monthly_cost=waste_proj.get("total_monthly_waste_cost", 0),
            waste_savings_monthly=waste_savings.get("total_savings_monthly", 0),
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


def _build_comparison(current_result, prev_snapshot, baseline_snapshot=None, all_snapshots=None):
    """Build a rich comparison dict with baseline, item movers, and cumulative savings."""
    curr_summary = (current_result.get("customer") or {}).get("summary") or {}
    curr_waste = (current_result.get("waste") or {}).get("waste_projection") or {}
    curr_savings = (current_result.get("waste") or {}).get("savings") or {}

    rev = curr_summary.get("avg_daily_revenue", 0) or 0
    prev_rev = prev_snapshot["avg_daily_revenue"] or 0
    ticket = curr_summary.get("avg_ticket_size", 0) or 0
    prev_ticket = prev_snapshot["avg_ticket_size"] or 0
    txns = curr_summary.get("avg_daily_transactions", 0) or 0
    prev_txns = prev_snapshot["avg_daily_transactions"] or 0

    waste_units_curr = curr_waste.get("total_daily_waste_units", 0) or 0
    waste_units_prev = prev_snapshot["waste_units_daily"] or 0
    waste_cost_curr = curr_waste.get("total_monthly_waste_cost", 0) or 0
    waste_cost_prev = prev_snapshot["waste_monthly_cost"] or 0

    # Baseline comparisons
    baseline_rev = (baseline_snapshot["avg_daily_revenue"] or 0) if baseline_snapshot else None
    baseline_ticket = (baseline_snapshot["avg_ticket_size"] or 0) if baseline_snapshot else None
    baseline_waste_units = (baseline_snapshot["waste_units_daily"] or 0) if baseline_snapshot else None
    baseline_waste_cost = (baseline_snapshot["waste_monthly_cost"] or 0) if baseline_snapshot else None

    # Cumulative savings estimate (sum of waste_savings_monthly across all weeks)
    cumulative_savings = 0
    weeks_tracked = 0
    if all_snapshots:
        for snap in all_snapshots:
            s = snap["waste_savings_monthly"] or 0
            if s > 0:
                cumulative_savings += s
                weeks_tracked += 1
    # Convert monthly savings to per-week (rough: monthly / 4.3)
    cumulative_weekly_savings = round(cumulative_savings / 4.3, 2) if cumulative_savings else 0

    # Item-level movers (compare top items between current and previous)
    movers = _build_item_movers(current_result, prev_snapshot)

    # Weekly action items
    actions = _build_weekly_actions(current_result, prev_snapshot, baseline_snapshot)

    return {
        "revenue": {
            "current": rev,
            "previous": prev_rev,
            "change": round(rev - prev_rev, 2),
            "baseline": baseline_rev,
            "baseline_change": round(rev - baseline_rev, 2) if baseline_rev is not None else None,
        },
        "ticket": {
            "current": ticket,
            "previous": prev_ticket,
            "change": round(ticket - prev_ticket, 2),
            "baseline": baseline_ticket,
            "baseline_change": round(ticket - baseline_ticket, 2) if baseline_ticket is not None else None,
        },
        "transactions": {
            "current": txns,
            "previous": prev_txns,
            "change": round(txns - prev_txns, 1),
        },
        "waste_units": {
            "current": waste_units_curr,
            "previous": waste_units_prev,
            "change": round(waste_units_curr - waste_units_prev, 1),
            "baseline": baseline_waste_units,
            "baseline_change": round(waste_units_curr - baseline_waste_units, 1) if baseline_waste_units is not None else None,
        },
        "waste_cost": {
            "current": waste_cost_curr,
            "previous": waste_cost_prev,
            "change": round(waste_cost_curr - waste_cost_prev, 2),
            "baseline": baseline_waste_cost,
            "baseline_change": round(waste_cost_curr - baseline_waste_cost, 2) if baseline_waste_cost is not None else None,
        },
        "cumulative_savings": {
            "total": round(cumulative_weekly_savings, 0),
            "weeks": weeks_tracked,
            "monthly_rate": round(curr_savings.get("total_savings_monthly", 0), 0),
        },
        "movers": movers,
        "actions": actions,
    }


def _build_item_movers(current_result, prev_snapshot):
    """Find the top items that changed the most between this week and last."""
    from ..analysis_runner import serialize_results
    customer = (current_result.get("customer") or {})

    # Get current items — might be a DataFrame or list
    curr_items = customer.get("all_items")
    if curr_items is None:
        curr_items = customer.get("top_items")
    # Serialize if it's a DataFrame
    curr_items = serialize_results(curr_items) if curr_items is not None else []
    if not curr_items:
        curr_items = []

    prev_items_json = prev_snapshot["customer_results"] if prev_snapshot else None

    if not curr_items or not prev_items_json:
        return []

    try:
        prev_customer = json.loads(prev_items_json) if isinstance(prev_items_json, str) else prev_items_json
        prev_items = prev_customer.get("all_items") or prev_customer.get("top_items") or []
    except (json.JSONDecodeError, TypeError):
        return []

    # Build lookup: item name -> revenue
    prev_lookup = {}
    for item in prev_items:
        name = item.get("item") or item.get("index") or ""
        prev_lookup[name] = item.get("revenue", 0) or 0

    # Calculate changes
    movers = []
    for item in curr_items:
        name = item.get("item") or item.get("index") or ""
        curr_rev = item.get("revenue", 0) or 0
        prev_rev = prev_lookup.get(name, 0)
        if prev_rev > 0:
            change_pct = round((curr_rev - prev_rev) / prev_rev * 100, 1)
            change_abs = round(curr_rev - prev_rev, 2)
            if abs(change_pct) >= 5:  # Only show meaningful changes
                movers.append({
                    "item": name,
                    "current_revenue": curr_rev,
                    "previous_revenue": prev_rev,
                    "change_pct": change_pct,
                    "change_abs": change_abs,
                    "direction": "up" if change_pct > 0 else "down",
                })

    # Sort by absolute change, return top 4
    movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return movers[:4]


def _build_weekly_actions(current_result, prev_snapshot, baseline_snapshot=None):
    """Generate 2-3 specific action items based on this week's changes."""
    actions = []

    curr_waste = (current_result.get("waste") or {}).get("waste_projection") or {}
    curr_items = curr_waste.get("items") or []

    # Action 1: Top waste item
    if curr_items:
        top = curr_items[0]
        actions.append({
            "type": "waste",
            "text": f"Reduce {top['item']} orders from {top['current_order']} to {top['recommended_order']}/day — saves ~${top['monthly_waste_cost']:.0f}/month",
        })

    # Action 2: Revenue change insight
    curr_summary = (current_result.get("customer") or {}).get("summary") or {}
    curr_rev = curr_summary.get("avg_daily_revenue", 0) or 0
    prev_rev = (prev_snapshot["avg_daily_revenue"] or 0) if prev_snapshot else 0
    if prev_rev > 0:
        rev_change_pct = (curr_rev - prev_rev) / prev_rev * 100
        if rev_change_pct < -5:
            actions.append({
                "type": "revenue",
                "text": f"Revenue dipped {rev_change_pct:.1f}% this week. Check if foot traffic dropped or if a popular item was unavailable.",
            })
        elif rev_change_pct > 5:
            actions.append({
                "type": "revenue",
                "text": f"Revenue is up {rev_change_pct:.1f}% — great week. Look at what drove it and consider doubling down.",
            })

    # Action 3: Baseline progress
    if baseline_snapshot:
        base_waste = baseline_snapshot["waste_monthly_cost"] or 0
        curr_waste_cost = curr_waste.get("total_monthly_waste_cost", 0) or 0
        if base_waste > 0 and curr_waste_cost < base_waste:
            reduction_pct = round((base_waste - curr_waste_cost) / base_waste * 100, 0)
            actions.append({
                "type": "progress",
                "text": f"Waste is down {reduction_pct:.0f}% since your baseline. Keep optimizing your ordering.",
            })
        elif base_waste > 0 and curr_waste_cost >= base_waste:
            actions.append({
                "type": "progress",
                "text": "Waste hasn't improved since baseline. Review the order recommendations in your report and try adjusting this week.",
            })

    return actions
