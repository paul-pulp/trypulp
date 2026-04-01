"""
PulpIQ Waste Analysis
Analyzes perishable sales patterns, milk usage, slow-moving items,
sell-through rates, day-of-week ordering patterns, and recommends
specific ordering quantities to reduce waste.

Dynamically adapts to any cafe's product categories and menu items
via keyword-based classification (see product_classifier.py).
"""

import pandas as pd
import numpy as np
from pathlib import Path

from product_classifier import (
    add_semantic_group, estimate_milk_usage, milk_cost_per_oz, get_costs,
)

# Typical perishable shelf life (hours from morning prep)
PERISHABLE_SHELF_LIFE_HRS = 10

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _normalize_columns(df):
    """Rename columns to canonical lowercase names so any POS export works."""
    from validate_data import COLUMN_ALIASES, _normalize
    rename_map = {}
    used_canonical = set()
    for col in df.columns:
        canonical = COLUMN_ALIASES.get(_normalize(col))
        if canonical and col != canonical and canonical not in used_canonical:
            rename_map[col] = canonical
            used_canonical.add(canonical)
        elif canonical:
            used_canonical.add(canonical if col == canonical else col)
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def load_data(csv_path):
    """Load and prepare sales data from a POS CSV export."""
    df = pd.read_csv(csv_path)
    df = _normalize_columns(df)
    df["date"] = pd.to_datetime(df["date"])
    df["hour"] = pd.to_datetime(df["time"], format="mixed").dt.hour
    df["day_of_week"] = df["date"].dt.day_name()
    df = add_semantic_group(df)
    return df


def analyze_perishable_sales_by_hour(df):
    """Break down perishable sales by hour to find when they sell and when they don't."""
    perishables = df[df["_group"] == "perishable_food"].copy()
    if perishables.empty:
        return {"hourly_sales": pd.DataFrame(), "summary": "No perishable food data found."}

    total_days = df["date"].nunique()
    hourly = (
        perishables.groupby("hour")
        .agg(units_sold=("quantity", "sum"), revenue=("price", "sum"))
        .reindex(range(df["hour"].min(), df["hour"].max() + 1), fill_value=0)
    )
    hourly["avg_units_per_day"] = (hourly["units_sold"] / total_days).round(1)
    hourly["avg_revenue_per_day"] = (hourly["revenue"] / total_days).round(2)

    peak_hour = hourly["units_sold"].idxmax()
    dead_hours = hourly[hourly["units_sold"] == 0].index.tolist()

    # Find the last hour with any sales
    selling_hours = hourly[hourly["units_sold"] > 0].index
    last_sale_hour = int(selling_hours.max()) if len(selling_hours) > 0 else None

    return {
        "hourly_sales": hourly,
        "peak_hour": peak_hour,
        "dead_hours": dead_hours,
        "last_sale_hour": last_sale_hour,
        "total_days": total_days,
    }


def identify_slow_movers(df, bottom_n=3):
    """Find the lowest-selling perishable items that may be generating waste."""
    perishables = df[df["_group"] == "perishable_food"]
    if perishables.empty:
        return pd.DataFrame()

    total_days = df["date"].nunique()
    item_sales = (
        perishables.groupby("item")
        .agg(
            total_units=("quantity", "sum"),
            total_revenue=("price", "sum"),
            days_with_sales=("date", "nunique"),
        )
        .sort_values("total_units")
    )
    item_sales["avg_units_per_day"] = (item_sales["total_units"] / total_days).round(1)
    item_sales["sell_through_pct"] = (
        (item_sales["days_with_sales"] / total_days) * 100
    ).round(0)

    return item_sales.head(bottom_n)


def sell_through_rates(df):
    """Compare sell-through rates for all perishable items.

    Sell-through = % of days the item actually sold at least 1 unit.
    Low sell-through = high waste risk.
    """
    perishable = df[df["_group"] == "perishable_food"].copy()
    if perishable.empty:
        return pd.DataFrame()

    total_days = df["date"].nunique()
    rates = (
        perishable.groupby("item")
        .agg(
            category=("category", "first") if "category" in df.columns else ("item", "first"),
            total_units=("quantity", "sum"),
            total_revenue=("price", "sum"),
            days_with_sales=("date", "nunique"),
            avg_price=("price", "mean"),
        )
    )
    rates["avg_units_per_day"] = (rates["total_units"] / total_days).round(1)
    rates["sell_through_pct"] = ((rates["days_with_sales"] / total_days) * 100).round(0)
    rates["avg_price"] = (rates["total_revenue"] / rates["total_units"]).round(2)

    # Flag risk level
    rates["waste_risk"] = rates["sell_through_pct"].apply(
        lambda pct: "HIGH" if pct < 50 else ("MEDIUM" if pct < 75 else "LOW")
    )

    return rates.sort_values("sell_through_pct")


def day_of_week_patterns(df):
    """Identify which items sell more/less on specific days.

    Returns per-item, per-day averages so ordering can be day-specific.
    """
    perishables = df[df["_group"] == "perishable_food"].copy()
    if perishables.empty:
        return {"by_item_day": pd.DataFrame(), "recommendations": []}

    total_days = df["date"].nunique()

    # Count how many of each weekday we have data for
    day_counts = df.groupby("day_of_week")["date"].nunique()

    # Sales per item per day-of-week
    daily_item = (
        perishables.groupby(["day_of_week", "item"])["quantity"]
        .sum()
        .unstack(fill_value=0)
    )
    # Normalize by number of that weekday observed
    daily_item = daily_item.astype(float)
    for day in daily_item.index:
        if day in day_counts.index and day_counts[day] > 0:
            daily_item.loc[day] = (daily_item.loc[day] / day_counts[day]).round(1)

    # Reorder days
    daily_item = daily_item.reindex([d for d in DAY_ORDER if d in daily_item.index])

    # Generate day-specific recommendations
    recommendations = []
    for item in daily_item.columns:
        col = daily_item[item]
        if col.max() == 0:
            continue
        avg = col.mean()
        best_day = col.idxmax()
        worst_day = col.idxmin()
        if avg > 0 and col.max() >= avg * 1.3:
            recommendations.append({
                "item": item,
                "type": "increase",
                "day": best_day,
                "avg_qty": round(col[best_day], 1),
                "overall_avg": round(avg, 1),
                "message": (
                    f"Order more {item} on {best_day}s — "
                    f"sells {col[best_day]:.1f}/day vs {avg:.1f} avg"
                ),
            })
        if avg > 0 and col.min() <= avg * 0.5:
            recommendations.append({
                "item": item,
                "type": "decrease",
                "day": worst_day,
                "avg_qty": round(col[worst_day], 1),
                "overall_avg": round(avg, 1),
                "message": (
                    f"Cut {item} on {worst_day}s — "
                    f"only {col[worst_day]:.1f}/day vs {avg:.1f} avg"
                ),
            })

    return {"by_item_day": daily_item, "recommendations": recommendations}


def calculate_milk_usage(df, cost_overrides=None):
    """Estimate daily milk consumption by type (dairy, oat, almond, etc.).

    Dynamically detects milk types from item names instead of using a
    hardcoded drink list. Works with any menu.
    """
    beverages = df[df["_group"] == "beverage"].copy()
    if beverages.empty:
        return {}

    costs = get_costs(cost_overrides)
    total_days = df["date"].nunique()

    # Estimate milk for every beverage row
    milk_totals = {}  # milk_type -> total_oz
    for _, row in beverages.iterrows():
        usage = estimate_milk_usage(row["item"])
        if usage["oz"] > 0:
            milk_type = usage["milk_type"]
            milk_totals[milk_type] = milk_totals.get(milk_type, 0) + usage["oz"] * row["quantity"]

    # Remove "none" type
    milk_totals.pop("none", None)

    if not milk_totals:
        return {}

    total_oz = sum(milk_totals.values())

    # Build per-type breakdown
    by_type = {}
    for milk_type, total in sorted(milk_totals.items(), key=lambda x: -x[1]):
        daily_oz = total / total_days
        cost_oz = milk_cost_per_oz(milk_type, costs)
        daily_cost = daily_oz * cost_oz

        # Dairy → gallons (128oz), alt milks → cartons (64oz)
        if milk_type == "dairy":
            unit_name = "gallons"
            unit_size = 128
        else:
            unit_name = "cartons"
            unit_size = 64

        daily_units = daily_oz / unit_size
        recommended_units = round(daily_units * 1.1, 1)

        by_type[milk_type] = {
            "daily_oz": round(daily_oz, 1),
            "daily_units": round(daily_units, 2),
            "unit_name": unit_name,
            "daily_cost": round(daily_cost, 2),
            "recommended_units_per_day": recommended_units,
            "pct_of_milk": round(total / total_oz * 100, 1) if total_oz > 0 else 0,
        }

    # Build backward-compatible keys for dairy/oat (report_generator uses these)
    dairy = by_type.get("dairy", {})
    oat = by_type.get("oat", {})

    return {
        "by_type": by_type,
        # backward-compatible flat keys
        "daily_dairy_oz": dairy.get("daily_oz", 0),
        "daily_oat_oz": oat.get("daily_oz", 0),
        "daily_dairy_gallons": dairy.get("daily_units", 0),
        "daily_oat_cartons": oat.get("daily_units", 0),
        "oat_milk_pct": oat.get("pct_of_milk", 0),
        "daily_dairy_cost": dairy.get("daily_cost", 0),
        "daily_oat_cost": oat.get("daily_cost", 0),
        "recommended_dairy_gal_per_day": dairy.get("recommended_units_per_day", 0),
        "recommended_oat_cartons_per_day": oat.get("recommended_units_per_day", 0),
    }


def recommend_order_quantities(df, cost_overrides=None):
    """Recommend daily perishable prep/order quantities based on actual sales.

    Returns specific 'order X instead of Y' numbers, not percentages.
    """
    costs = get_costs(cost_overrides)
    perishables = df[df["_group"] == "perishable_food"]
    if perishables.empty:
        return pd.DataFrame()

    total_days = df["date"].nunique()
    daily_sales = perishables.groupby(["date", "item"])["quantity"].sum().reset_index()

    # Ensure every item appears for every date (fill missing days with 0)
    all_dates = df["date"].unique()
    all_items = perishables["item"].unique()
    full_index = pd.MultiIndex.from_product([all_dates, all_items], names=["date", "item"])
    daily_sales = (
        daily_sales.set_index(["date", "item"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    item_stats = (
        daily_sales.groupby("item")["quantity"]
        .agg(["mean", "std", "max", "min"])
        .round(1)
    )

    # Days with zero sales for this item
    zero_days = daily_sales[daily_sales["quantity"] == 0].groupby("item").size()
    item_stats["zero_sale_days"] = zero_days.reindex(item_stats.index, fill_value=0).astype(int)
    item_stats["zero_sale_pct"] = ((item_stats["zero_sale_days"] / total_days) * 100).round(0)

    # Recommend: mean + 0.5*std (buffer for variance, but not full std to reduce waste)
    item_stats["recommended_qty"] = np.ceil(
        item_stats["mean"] + 0.5 * item_stats["std"].fillna(0)
    ).astype(int)
    # Ensure at least 1 if the item ever sold
    item_stats["recommended_qty"] = item_stats["recommended_qty"].clip(lower=1)

    # Current assumed order = max observed (shops tend to order for peak)
    item_stats["current_est_order"] = item_stats["max"].astype(int)
    item_stats["reduction"] = item_stats["current_est_order"] - item_stats["recommended_qty"]

    # Estimated daily waste under current ordering
    item_stats["est_daily_waste"] = (
        item_stats["current_est_order"] - item_stats["mean"]
    ).clip(lower=0).round(1)

    # Cost per item (average price * COGS ratio)
    cogs = costs["perishable_cogs_ratio"]
    perishables_copy = perishables.reset_index(drop=True).copy()
    perishables_copy["_unit_price"] = perishables_copy["price"] / perishables_copy["quantity"]
    item_prices = perishables_copy.groupby("item")["_unit_price"].mean()
    item_stats["unit_cost"] = (item_prices * cogs).round(2)
    item_stats["daily_waste_cost"] = (item_stats["est_daily_waste"] * item_stats["unit_cost"]).round(2)
    op_days = _operating_days_per_month(df)
    item_stats["monthly_waste_cost"] = (item_stats["daily_waste_cost"] * op_days).round(2)

    return item_stats


def project_waste(df, cost_overrides=None):
    """Project total waste based on current ordering patterns."""
    recs = recommend_order_quantities(df, cost_overrides)
    if recs.empty:
        return {}

    total_daily_waste_units = recs["est_daily_waste"].sum()
    total_daily_waste_cost = recs["daily_waste_cost"].sum()

    # Build per-item breakdown
    items = []
    for item, row in recs.iterrows():
        if row["est_daily_waste"] > 0:
            items.append({
                "item": item,
                "current_order": int(row["current_est_order"]),
                "avg_sold": round(row["mean"], 1),
                "recommended_order": int(row["recommended_qty"]),
                "daily_waste_units": round(row["est_daily_waste"], 1),
                "daily_waste_cost": round(row["daily_waste_cost"], 2),
                "monthly_waste_cost": round(row["monthly_waste_cost"], 2),
            })

    return {
        "items": sorted(items, key=lambda x: x["monthly_waste_cost"], reverse=True),
        "total_daily_waste_units": round(total_daily_waste_units, 1),
        "total_daily_waste_cost": round(total_daily_waste_cost, 2),
        "total_monthly_waste_cost": round(recs["monthly_waste_cost"].sum(), 2),
    }


def estimate_waste_savings(df, cost_overrides=None):
    """Estimate monthly $ savings from optimized ordering."""
    costs = get_costs(cost_overrides)
    cogs = costs["perishable_cogs_ratio"]

    perishables = df[df["_group"] == "perishable_food"]
    if perishables.empty:
        return {}

    total_days = df["date"].nunique()

    # Use the full daily_sales with zero-filled days for accuracy
    all_dates = df["date"].unique()
    all_items = perishables["item"].unique()
    daily_sales = perishables.groupby(["date", "item"])["quantity"].sum().reset_index()
    full_index = pd.MultiIndex.from_product([all_dates, all_items], names=["date", "item"])
    daily_sales = (
        daily_sales.set_index(["date", "item"])
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    item_peaks = daily_sales.groupby("item")["quantity"].max()
    item_means = daily_sales.groupby("item")["quantity"].mean()
    perishables_ws = perishables.reset_index(drop=True).copy()
    perishables_ws["_unit_price"] = perishables_ws["price"] / perishables_ws["quantity"]
    item_prices = perishables_ws.groupby("item")["_unit_price"].mean()

    op_days = _operating_days_per_month(df)

    daily_waste_units = (item_peaks - item_means).clip(lower=0)
    daily_waste_cost = (daily_waste_units * item_prices * cogs).sum()
    monthly_waste_cost = daily_waste_cost * op_days

    # With optimization: order at mean + 0.5*std instead of peak
    item_stds = daily_sales.groupby("item")["quantity"].std().fillna(0)
    optimized_order = np.ceil(item_means + 0.5 * item_stds).clip(lower=1)
    optimized_waste = (optimized_order - item_means).clip(lower=0)
    optimized_waste_cost = (optimized_waste * item_prices * cogs).sum()
    optimized_monthly = optimized_waste_cost * op_days

    # Savings based on data-driven ordering improvements only (no guesses)
    ordering_savings = round(monthly_waste_cost - optimized_monthly, 2)

    return {
        "current_pastry_waste_monthly": round(monthly_waste_cost, 2),
        "optimized_pastry_waste_monthly": round(optimized_monthly, 2),
        "pastry_savings_monthly": ordering_savings,
        "milk_waste_savings_monthly": 0,  # removed — was an unsupported estimate
        "total_savings_monthly": round(ordering_savings, 2
        ),
    }


def _operating_days_per_month(df):
    """Calculate how many days per month the cafe actually operates.

    Uses ratio of sales days to calendar days in the data range, projected to 30 days.
    A cafe open 5 days/week = ~22 operating days/month instead of 30.
    """
    unique_days = df["date"].nunique()
    if unique_days <= 1:
        return 30
    date_range = (df["date"].max() - df["date"].min()).days + 1
    if date_range <= 0:
        return 30
    ratio = unique_days / date_range
    return max(1, round(ratio * 30))


def run(csv_path, cost_overrides=None):
    """Run the full waste analysis and return structured results."""
    df = load_data(csv_path)
    return {
        "pastry_by_hour": analyze_perishable_sales_by_hour(df),
        "slow_movers": identify_slow_movers(df),
        "sell_through": sell_through_rates(df),
        "day_of_week": day_of_week_patterns(df),
        "milk_usage": calculate_milk_usage(df, cost_overrides),
        "order_recommendations": recommend_order_quantities(df, cost_overrides),
        "waste_projection": project_waste(df, cost_overrides),
        "savings": estimate_waste_savings(df, cost_overrides),
        "data_range": {
            "start": str(df["date"].min().date()),
            "end": str(df["date"].max().date()),
            "days": df["date"].nunique(),
        },
    }


if __name__ == "__main__":
    import sys

    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parents[2] / "data" / "sample-data" / "sample-cafe-sales.csv"
    )
    results = run(csv_path)

    print("=" * 60)
    print("PULPIQ WASTE ANALYSIS REPORT")
    print("=" * 60)
    print(f"\nData: {results['data_range']['start']} to {results['data_range']['end']}"
          f" ({results['data_range']['days']} days)\n")

    print("--- PERISHABLE SALES BY HOUR ---")
    perishable = results["pastry_by_hour"]
    if not perishable["hourly_sales"].empty:
        print(perishable["hourly_sales"][["avg_units_per_day", "avg_revenue_per_day"]].to_string())
        print(f"\nPeak hour: {perishable['peak_hour']}:00")
        if perishable["dead_hours"]:
            print(f"No sales: {', '.join(f'{h}:00' for h in perishable['dead_hours'])}")
        if perishable["last_sale_hour"]:
            print(f"Last sale typically by: {perishable['last_sale_hour']}:00")

    print("\n--- SELL-THROUGH RATES (all perishables) ---")
    st = results["sell_through"]
    if not st.empty:
        print(st[["category", "avg_units_per_day", "sell_through_pct", "waste_risk"]].to_string())

    print("\n--- SLOW-MOVING ITEMS ---")
    sm = results["slow_movers"]
    if not sm.empty:
        print(sm[["avg_units_per_day", "sell_through_pct"]].to_string())

    print("\n--- DAY-OF-WEEK PATTERNS ---")
    dow = results["day_of_week"]
    if not dow["by_item_day"].empty:
        print(dow["by_item_day"].to_string())
    if dow["recommendations"]:
        print("\n  Day-specific suggestions:")
        for rec in dow["recommendations"]:
            print(f"    -> {rec['message']}")

    print("\n--- MILK USAGE (daily avg) ---")
    milk = results["milk_usage"]
    if milk.get("by_type"):
        for mtype, mdata in milk["by_type"].items():
            print(f"{mtype.title()}: {mdata['daily_oz']} oz ({mdata['daily_units']} {mdata['unit_name']}) "
                  f"= ${mdata['daily_cost']}/day ({mdata['pct_of_milk']}% of milk)")
            print(f"  -> Order: {mdata['recommended_units_per_day']} {mdata['unit_name']}/day")

    print("\n--- ORDER RECOMMENDATIONS ---")
    recs = results["order_recommendations"]
    if not recs.empty:
        cols = ["mean", "current_est_order", "recommended_qty", "reduction", "est_daily_waste", "monthly_waste_cost"]
        print(recs[cols].to_string())

    print("\n--- WASTE PROJECTION (current ordering patterns) ---")
    wp = results["waste_projection"]
    if wp and wp.get("items"):
        for item in wp["items"]:
            print(f"  {item['item']}: ordering ~{item['current_order']}, selling ~{item['avg_sold']}/day "
                  f"-> {item['daily_waste_units']} wasted/day (${item['monthly_waste_cost']}/mo)")
        print(f"\n  TOTAL projected waste: {wp['total_daily_waste_units']} units/day, "
              f"${wp['total_monthly_waste_cost']}/mo")

    print("\n--- ESTIMATED MONTHLY SAVINGS ---")
    savings = results["savings"]
    print(f"Perishable waste reduction: ${savings['pastry_savings_monthly']:.2f}/mo")
    print(f"Milk waste reduction:       ${savings['milk_waste_savings_monthly']:.2f}/mo")
    print(f"TOTAL POTENTIAL SAVINGS:    ${savings['total_savings_monthly']:.2f}/mo")
