"""
PulpIQ Product Classifier
Auto-detects product categories, milk types, and drink profiles
from item names using keyword matching. No configuration needed —
works out of the box with any cafe CSV.
"""


# ── Category Classification ────────────────────────────────────────────────
# Maps keyword fragments (matched against the CSV's category column) to
# semantic groups used internally by the analysis modules.

CATEGORY_KEYWORDS = {
    "beverage": [
        "beverage", "drink", "coffee", "tea", "juice", "smoothie",
        "cold drink", "hot drink", "espresso bar", "bar",
    ],
    "perishable_food": [
        "pastry", "bakery", "baked", "food", "sandwich", "salad",
        "wrap", "pizza", "soup", "deli", "fresh", "prepared",
        "kitchen", "grab and go", "grab & go", "breakfast",
        "lunch", "brunch", "snack",
    ],
    "non_perishable": [
        "retail", "merch", "merchandise", "packaged", "bottle",
        "gift", "equipment", "supply",
    ],
}

# ── Item-Level Classification ──────────────────────────────────────────────
# When the category column is missing or too coarse, classify by item name.

BEVERAGE_ITEM_KEYWORDS = [
    "latte", "cappuccino", "americano", "espresso", "coffee", "cold brew",
    "mocha", "macchiato", "flat white", "tea", "chai", "matcha",
    "smoothie", "juice", "frappuccino", "frappe", "cortado", "affogato",
    "hot chocolate", "cocoa", "lemonade", "soda", "agua fresca",
    "boba", "bubble tea", "horchata",
]

PERISHABLE_ITEM_KEYWORDS = [
    "croissant", "muffin", "scone", "bread", "cookie", "danish",
    "bagel", "cake", "pie", "tart", "roll", "sandwich", "wrap",
    "salad", "bowl", "panini", "quiche", "toast", "waffle", "pancake",
    "banana bread", "brownie", "donut", "doughnut", "biscotti",
    "pizza", "slice", "empanada", "turnover", "pretzel",
]


# ── Milk Usage Profiles ────────────────────────────────────────────────────
# Keyed by keyword found in the item name. Longest match wins.
# oz = estimated milk per drink, default_milk = assumed type unless overridden.

MILK_PROFILES = {
    "latte":          {"oz": 10, "default_milk": "dairy"},
    "flat white":     {"oz": 8,  "default_milk": "dairy"},
    "cappuccino":     {"oz": 6,  "default_milk": "dairy"},
    "mocha":          {"oz": 8,  "default_milk": "dairy"},
    "macchiato":      {"oz": 2,  "default_milk": "dairy"},
    "cortado":        {"oz": 4,  "default_milk": "dairy"},
    "hot chocolate":  {"oz": 10, "default_milk": "dairy"},
    "cocoa":          {"oz": 10, "default_milk": "dairy"},
    "chai":           {"oz": 8,  "default_milk": "dairy"},
    "matcha":         {"oz": 10, "default_milk": "dairy"},
    "drip coffee":    {"oz": 1,  "default_milk": "dairy"},
    "coffee":         {"oz": 1,  "default_milk": "dairy"},
    "cold brew":      {"oz": 0,  "default_milk": "none"},
    "americano":      {"oz": 0,  "default_milk": "none"},
    "espresso":       {"oz": 0,  "default_milk": "none"},
    "smoothie":       {"oz": 6,  "default_milk": "dairy"},
    "frappuccino":    {"oz": 8,  "default_milk": "dairy"},
    "frappe":         {"oz": 8,  "default_milk": "dairy"},
    "affogato":       {"oz": 2,  "default_milk": "dairy"},
}

# Sorted longest-first so "flat white" matches before "white", etc.
_MILK_PROFILE_KEYS = sorted(MILK_PROFILES.keys(), key=len, reverse=True)

ICED_MILK_BONUS_OZ = 2  # iced drinks use more milk (bigger cup)

# Keywords in item name that override the default milk type.
ALT_MILK_KEYWORDS = {
    "oat milk":     "oat",
    "oat":          "oat",
    "almond milk":  "almond",
    "almond":       "almond",
    "soy milk":     "soy",
    "soy":          "soy",
    "coconut milk": "coconut",
    "coconut":      "coconut",
}
# Sorted longest-first so "oat milk" matches before "oat"
_ALT_MILK_KEYS = sorted(ALT_MILK_KEYWORDS.keys(), key=len, reverse=True)


# ── Temperature Classification ─────────────────────────────────────────────

ICED_KEYWORDS = ["iced", "cold brew", "cold", "frozen", "frappuccino", "frappe"]
HOT_KEYWORDS = [
    "latte", "cappuccino", "americano", "espresso", "drip", "mocha",
    "macchiato", "flat white", "cortado", "chai", "hot chocolate", "tea",
]


# ── Cost Defaults ──────────────────────────────────────────────────────────

DEFAULT_COSTS = {
    # Toronto, Canada pricing (CAD) — sourced from Sysco/Saputo, Oatly/Pacific
    # Barista wholesale case pricing, Statistics Canada, and Ontario ESA (2025-2026)
    "dairy_cost_per_oz": 0.04,      # ~$5.10 CAD/gallon via foodservice distributor
    "oat_cost_per_oz": 0.15,        # ~$4.50 CAD/946mL carton (Oatly Barista case)
    "almond_cost_per_oz": 0.14,     # ~$4.62 CAD/946mL carton (Pacific Barista)
    "soy_cost_per_oz": 0.12,        # ~$3.83 CAD/946mL carton (Pacific Barista)
    "coconut_cost_per_oz": 0.15,    # ~$4.75 CAD/946mL carton (Pacific Barista)
    "perishable_cogs_ratio": 0.30,  # 30% blended COGS (beverage-heavy cafe)
    "hourly_wage": 18.50,           # Toronto indie cafe avg barista wage (CAD)
    "payroll_overhead": 1.17,       # 17% Ontario: CPP + EI + vacation + holidays + WSIB
}


# ── Public API ─────────────────────────────────────────────────────────────

def classify_category(category_name):
    """Classify a category string into a semantic group.

    Returns: "beverage", "perishable_food", "non_perishable", or "unknown".
    """
    lower = category_name.strip().lower()
    for group, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return group
    return "unknown"


def classify_item(item_name):
    """Classify an item by its name into a semantic group.

    Returns: "beverage", "perishable_food", or "unknown".
    """
    lower = item_name.strip().lower()
    for kw in BEVERAGE_ITEM_KEYWORDS:
        if kw in lower:
            return "beverage"
    for kw in PERISHABLE_ITEM_KEYWORDS:
        if kw in lower:
            return "perishable_food"
    return "unknown"


def add_semantic_group(df):
    """Add a '_group' column to the DataFrame with semantic classification.

    Uses the category column first, then falls back to item name matching.
    """
    has_category = "category" in df.columns

    if has_category:
        # Build a category -> group lookup (one call per unique category)
        cat_map = {
            cat: classify_category(cat)
            for cat in df["category"].dropna().unique()
        }
        df["_group"] = df["category"].map(cat_map).fillna("unknown")
    else:
        df["_group"] = "unknown"

    # For any "unknown" rows, try item-name classification
    unknown_mask = df["_group"] == "unknown"
    if unknown_mask.any():
        item_map = {
            item: classify_item(item)
            for item in df.loc[unknown_mask, "item"].unique()
        }
        df.loc[unknown_mask, "_group"] = df.loc[unknown_mask, "item"].map(item_map)

    return df


def classify_temperature(item_name):
    """Classify a drink as 'hot', 'iced', or 'unknown'."""
    lower = item_name.strip().lower()
    for kw in ICED_KEYWORDS:
        if kw in lower:
            return "iced"
    for kw in HOT_KEYWORDS:
        if kw in lower:
            return "hot"
    return "unknown"


def estimate_milk_usage(item_name):
    """Estimate milk usage for a single item.

    Returns: {"oz": float, "milk_type": str}
    milk_type is one of: "dairy", "oat", "almond", "soy", "coconut", "none"
    """
    lower = item_name.strip().lower()

    # Find the drink base profile
    oz = 0
    default_milk = "none"
    for key in _MILK_PROFILE_KEYS:
        if key in lower:
            profile = MILK_PROFILES[key]
            oz = profile["oz"]
            default_milk = profile["default_milk"]
            break

    if oz == 0:
        return {"oz": 0, "milk_type": "none"}

    # Iced bonus
    if any(kw in lower for kw in ICED_KEYWORDS):
        oz += ICED_MILK_BONUS_OZ

    # Check for alt-milk override
    milk_type = default_milk
    for kw in _ALT_MILK_KEYS:
        if kw in lower:
            milk_type = ALT_MILK_KEYWORDS[kw]
            break

    return {"oz": oz, "milk_type": milk_type}


def get_costs(overrides=None):
    """Return cost assumptions, merged with any user overrides."""
    costs = dict(DEFAULT_COSTS)
    if overrides:
        costs.update(overrides)
    costs["loaded_hourly"] = costs["hourly_wage"] * costs["payroll_overhead"]
    return costs


def milk_cost_per_oz(milk_type, costs=None):
    """Get the cost per oz for a given milk type."""
    if costs is None:
        costs = get_costs()
    key = f"{milk_type}_cost_per_oz"
    return costs.get(key, costs["dairy_cost_per_oz"])


# pandas is imported lazily to keep the module importable without it
import pandas as pd
