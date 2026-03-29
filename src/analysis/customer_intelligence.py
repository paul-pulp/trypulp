"""
PulpIQ Customer Intelligence
Analyzes top-selling items, revenue by category, payment preferences,
daily/hourly trends, hot vs iced drink patterns, time-of-day preferences,
and add-on popularity.
"""

import pandas as pd
from pathlib import Path

from product_classifier import add_semantic_group, classify_temperature

# Known add-on keywords that may appear in item names
ADD_ON_KEYWORDS = {
    "extra shot": "Extra Shot",
    "double shot": "Extra Shot",
    "vanilla": "Vanilla Syrup",
    "caramel": "Caramel Syrup",
    "hazelnut": "Hazelnut Syrup",
    "mocha": "Mocha Syrup",
    "oat milk": "Oat Milk",
    "almond milk": "Almond Milk",
    "soy milk": "Soy Milk",
    "decaf": "Decaf",
}

# Time-of-day buckets
TIME_BUCKETS = {
    "early_morning": (6, 8),   # 6:00-7:59
    "morning_rush": (8, 10),   # 8:00-9:59
    "late_morning": (10, 12),  # 10:00-11:59
    "lunch": (12, 14),         # 12:00-13:59
    "afternoon": (14, 16),     # 14:00-15:59
    "evening": (16, 19),       # 16:00-18:59
}


def _normalize_columns(df):
    """Rename columns to canonical lowercase names so any POS export works."""
    from validate_data import COLUMN_ALIASES, _normalize
    rename_map = {}
    for col in df.columns:
        canonical = COLUMN_ALIASES.get(_normalize(col))
        if canonical and col != canonical:
            rename_map[col] = canonical
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def load_data(csv_path):
    """Load and prepare sales data."""
    df = pd.read_csv(csv_path)
    df = _normalize_columns(df)
    df["date"] = pd.to_datetime(df["date"])
    df["hour"] = pd.to_datetime(df["time"], format="mixed").dt.hour
    df["day_of_week"] = df["date"].dt.day_name()
    df = add_semantic_group(df)
    return df


def _get_time_bucket(hour):
    """Map an hour to a named time bucket."""
    for bucket, (start, end) in TIME_BUCKETS.items():
        if start <= hour < end:
            return bucket
    return "other"


def top_selling_items(df, top_n=10):
    """Rank items by units sold and revenue."""
    items = (
        df.groupby("item")
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("price", "sum"),
            avg_price=("price", "mean"),
            transaction_count=("time", "count"),
        )
        .sort_values("revenue", ascending=False)
    )
    items["avg_price"] = (items["revenue"] / items["units_sold"]).round(2)
    items["revenue_pct"] = (items["revenue"] / items["revenue"].sum() * 100).round(1)
    return items.head(top_n)


def revenue_by_category(df):
    """Break down revenue and volume by category."""
    cats = (
        df.groupby("category")
        .agg(
            units_sold=("quantity", "sum"),
            revenue=("price", "sum"),
            item_count=("item", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )
    cats["revenue_pct"] = (cats["revenue"] / cats["revenue"].sum() * 100).round(1)
    cats["avg_ticket"] = (cats["revenue"] / cats["units_sold"]).round(2)
    return cats


def payment_method_breakdown(df):
    """Analyze payment method preferences."""
    txns = df.groupby(["date", "time", "payment_method"]).agg(
        total=("price", "sum")
    ).reset_index()

    methods = (
        txns.groupby("payment_method")
        .agg(
            transaction_count=("total", "count"),
            total_revenue=("total", "sum"),
        )
        .sort_values("total_revenue", ascending=False)
    )
    methods["pct_of_transactions"] = (
        methods["transaction_count"] / methods["transaction_count"].sum() * 100
    ).round(1)
    methods["avg_transaction"] = (
        methods["total_revenue"] / methods["transaction_count"]
    ).round(2)
    return methods


def daily_trends(df):
    """Revenue and transaction patterns by day of week."""
    daily = (
        df.groupby(["date", "day_of_week"])
        .agg(revenue=("price", "sum"), items_sold=("quantity", "sum"))
        .reset_index()
    )
    by_dow = (
        daily.groupby("day_of_week")
        .agg(
            avg_revenue=("revenue", "mean"),
            avg_items=("items_sold", "mean"),
            days_observed=("date", "count"),
        )
        .round(2)
    )
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_dow = by_dow.reindex([d for d in day_order if d in by_dow.index])
    return by_dow


def hourly_trends(df):
    """Revenue patterns by hour."""
    hourly = (
        df.groupby("hour")
        .agg(
            total_revenue=("price", "sum"),
            total_units=("quantity", "sum"),
            transaction_count=("time", "nunique"),
        )
        .reindex(range(6, 19), fill_value=0)
    )
    total_days = df["date"].nunique()
    hourly["avg_revenue_per_day"] = (hourly["total_revenue"] / total_days).round(2)
    hourly["revenue_pct"] = (
        hourly["total_revenue"] / hourly["total_revenue"].sum() * 100
    ).round(1)
    return hourly


def hot_vs_iced_analysis(df):
    """Analyze hot vs iced drink patterns by time of day and day of week."""
    beverages = df[df["_group"] == "beverage"].copy()
    if beverages.empty:
        return {"summary": {}, "by_hour": pd.DataFrame(), "by_day": pd.DataFrame()}

    beverages["temperature"] = beverages["item"].apply(classify_temperature)
    total_days = df["date"].nunique()

    # Overall split
    temp_totals = (
        beverages.groupby("temperature")
        .agg(units=("quantity", "sum"), revenue=("price", "sum"))
    )
    total_units = temp_totals["units"].sum()
    summary = {}
    for temp in ["hot", "iced"]:
        if temp in temp_totals.index:
            units = int(temp_totals.loc[temp, "units"])
            summary[temp] = {
                "units": units,
                "pct": round(units / total_units * 100, 1) if total_units > 0 else 0,
                "revenue": round(temp_totals.loc[temp, "revenue"], 2),
                "avg_per_day": round(units / total_days, 1),
            }
        else:
            summary[temp] = {"units": 0, "pct": 0, "revenue": 0, "avg_per_day": 0}

    # By hour: when do iced drinks spike?
    by_hour = (
        beverages.groupby(["hour", "temperature"])
        .agg(units=("quantity", "sum"))
        .unstack(fill_value=0)
    )
    by_hour.columns = [col[1] for col in by_hour.columns]
    for col in ["hot", "iced"]:
        if col not in by_hour.columns:
            by_hour[col] = 0
    by_hour["iced_pct"] = (
        by_hour["iced"] / (by_hour["hot"] + by_hour["iced"]).replace(0, 1) * 100
    ).round(1)
    by_hour = by_hour.reindex(range(6, 19), fill_value=0)

    # By day of week
    by_day = (
        beverages.groupby(["day_of_week", "temperature"])
        .agg(units=("quantity", "sum"))
        .unstack(fill_value=0)
    )
    by_day.columns = [col[1] for col in by_day.columns]
    for col in ["hot", "iced"]:
        if col not in by_day.columns:
            by_day[col] = 0
    by_day["iced_pct"] = (
        by_day["iced"] / (by_day["hot"] + by_day["iced"]).replace(0, 1) * 100
    ).round(1)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = by_day.reindex([d for d in day_order if d in by_day.index])

    return {"summary": summary, "by_hour": by_hour, "by_day": by_day}


def time_of_day_preferences(df):
    """What sells during each part of the day (morning lattes, afternoon cold brew, etc)."""
    beverages = df[df["_group"] == "beverage"].copy()
    if beverages.empty:
        return {}

    beverages["time_bucket"] = beverages["hour"].apply(_get_time_bucket)
    total_days = df["date"].nunique()

    results = {}
    for bucket in TIME_BUCKETS:
        bucket_data = beverages[beverages["time_bucket"] == bucket]
        if bucket_data.empty:
            results[bucket] = {"top_items": [], "total_units": 0}
            continue

        top = (
            bucket_data.groupby("item")
            .agg(units=("quantity", "sum"), revenue=("price", "sum"))
            .sort_values("units", ascending=False)
        )
        total_units = int(top["units"].sum())
        top["pct"] = (top["units"] / total_units * 100).round(1)
        top["avg_per_day"] = (top["units"] / total_days).round(1)

        results[bucket] = {
            "top_items": [
                {
                    "item": item,
                    "units": int(row["units"]),
                    "pct": row["pct"],
                    "avg_per_day": row["avg_per_day"],
                }
                for item, row in top.head(5).iterrows()
            ],
            "total_units": total_units,
            "avg_per_day": round(total_units / total_days, 1),
        }

    return results


def detect_add_ons(df):
    """Detect add-on patterns from item names (e.g., 'Oat Milk Latte' -> oat milk add-on).

    Returns detected add-ons and a note about data limitations.
    """
    beverages = df[df["_group"] == "beverage"].copy()
    if beverages.empty:
        return {"detected": [], "note": "No beverage data found."}

    total_days = df["date"].nunique()
    detected = {}
    for _, row in beverages.iterrows():
        item_lower = row["item"].lower()
        for keyword, label in ADD_ON_KEYWORDS.items():
            if keyword in item_lower:
                if label not in detected:
                    detected[label] = {"units": 0, "revenue": 0.0}
                detected[label]["units"] += row["quantity"]
                detected[label]["revenue"] += row["price"]

    add_on_list = []
    total_bev_units = int(beverages["quantity"].sum())
    for label, data in sorted(detected.items(), key=lambda x: x[1]["units"], reverse=True):
        add_on_list.append({
            "add_on": label,
            "units": data["units"],
            "pct_of_beverages": round(data["units"] / total_bev_units * 100, 1) if total_bev_units > 0 else 0,
            "avg_per_day": round(data["units"] / total_days, 1),
            "revenue": round(data["revenue"], 2),
        })

    note = (
        "Add-ons detected from item names only. For detailed add-on tracking "
        "(extra shots, syrups, milk swaps), your POS should log modifiers as "
        "separate line items or in an add-on column."
    )

    return {"detected": add_on_list, "total_beverages": total_bev_units, "note": note}


def summary_stats(df):
    """High-level summary metrics."""
    total_days = df["date"].nunique()
    total_revenue = df["price"].sum()
    total_items = df["quantity"].sum()

    txn_count = df.groupby(["date", "time"]).ngroups
    avg_ticket = total_revenue / txn_count if txn_count > 0 else 0

    return {
        "total_revenue": round(total_revenue, 2),
        "total_items_sold": int(total_items),
        "total_transactions": txn_count,
        "total_days": total_days,
        "avg_daily_revenue": round(total_revenue / total_days, 2),
        "avg_daily_transactions": round(txn_count / total_days, 1),
        "avg_ticket_size": round(avg_ticket, 2),
        "unique_items": df["item"].nunique(),
    }


def run(csv_path):
    """Run the full customer intelligence analysis."""
    df = load_data(csv_path)
    return {
        "summary": summary_stats(df),
        "top_items": top_selling_items(df),
        "revenue_by_category": revenue_by_category(df),
        "payment_methods": payment_method_breakdown(df),
        "daily_trends": daily_trends(df),
        "hourly_trends": hourly_trends(df),
        "hot_vs_iced": hot_vs_iced_analysis(df),
        "time_of_day": time_of_day_preferences(df),
        "add_ons": detect_add_ons(df),
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
    print("PULPIQ CUSTOMER INTELLIGENCE REPORT")
    print("=" * 60)
    print(f"\nData: {results['data_range']['start']} to {results['data_range']['end']}"
          f" ({results['data_range']['days']} days)\n")

    print("--- SUMMARY ---")
    s = results["summary"]
    print(f"Total revenue:         ${s['total_revenue']:,.2f}")
    print(f"Total transactions:    {s['total_transactions']}")
    print(f"Avg daily revenue:     ${s['avg_daily_revenue']:,.2f}")
    print(f"Avg ticket size:       ${s['avg_ticket_size']:.2f}")
    print(f"Unique menu items:     {s['unique_items']}")

    print("\n--- TOP SELLING ITEMS ---")
    print(results["top_items"][["units_sold", "revenue", "revenue_pct"]].to_string())

    print("\n--- REVENUE BY CATEGORY ---")
    print(results["revenue_by_category"].to_string())

    print("\n--- PAYMENT METHODS ---")
    print(results["payment_methods"].to_string())

    print("\n--- DAILY TRENDS ---")
    print(results["daily_trends"].to_string())

    print("\n--- HOURLY REVENUE PATTERN ---")
    print(results["hourly_trends"][["avg_revenue_per_day", "revenue_pct"]].to_string())

    print("\n--- HOT vs ICED ---")
    hvi = results["hot_vs_iced"]
    for temp in ["hot", "iced"]:
        info = hvi["summary"].get(temp, {})
        print(f"  {temp.title()}: {info.get('units', 0)} units "
              f"({info.get('pct', 0)}%), {info.get('avg_per_day', 0)}/day")
    if not hvi["by_hour"].empty:
        print("\n  Iced % by hour:")
        for hour, row in hvi["by_hour"].iterrows():
            if row.get("iced", 0) + row.get("hot", 0) > 0:
                print(f"    {hour}:00 — {row.get('iced_pct', 0)}% iced")

    print("\n--- TIME-OF-DAY PREFERENCES ---")
    for bucket, data in results["time_of_day"].items():
        if data.get("top_items"):
            label = bucket.replace("_", " ").title()
            print(f"\n  {label} ({data['avg_per_day']} drinks/day):")
            for item in data["top_items"][:3]:
                print(f"    {item['item']}: {item['avg_per_day']}/day ({item['pct']}%)")

    print("\n--- ADD-ONS DETECTED ---")
    add_ons = results["add_ons"]
    if add_ons["detected"]:
        for ao in add_ons["detected"]:
            print(f"  {ao['add_on']}: {ao['units']} units ({ao['pct_of_beverages']}% of beverages)")
    print(f"  Note: {add_ons['note']}")
