"""
PulpIQ Data Validator
Validates cafe POS CSV exports before running analysis.
Catches column mismatches, missing data, bad values, and
insufficient date ranges — with specific fix suggestions.
"""

import sys
import csv
from pathlib import Path
from datetime import datetime, timedelta


# ── Column mapping ──────────────────────────────────────────────────────────
# Maps normalized (lowercase, stripped, common variations) to our canonical names.
# Left side = things cafes/POS systems actually export. Right side = what we need.
COLUMN_ALIASES = {
    # date
    "date": "date",
    "sale date": "date",
    "transaction date": "date",
    "trans date": "date",
    "order date": "date",
    # time
    "time": "time",
    "sale time": "time",
    "transaction time": "time",
    "trans time": "time",
    "order time": "time",
    # item
    "item": "item",
    "item name": "item",
    "product": "item",
    "product name": "item",
    "menu item": "item",
    "description": "item",
    # quantity
    "quantity": "quantity",
    "qty": "quantity",
    "units": "quantity",
    "count": "quantity",
    "units sold": "quantity",
    # price
    "price": "price",
    "total": "price",
    "amount": "price",
    "sale amount": "price",
    "total price": "price",
    "revenue": "price",
    "net sales": "price",
    "gross sales": "price",
    # optional but useful
    "category": "category",
    "type": "category",
    "item category": "category",
    "product category": "category",
    "payment method": "payment_method",
    "payment_method": "payment_method",
    "payment type": "payment_method",
    "tender": "payment_method",
    "location": "location",
    "store": "location",
    "store name": "location",
}

REQUIRED_COLUMNS = ["date", "time", "item", "quantity", "price"]
OPTIONAL_COLUMNS = ["category", "payment_method", "location"]

# ── Thresholds ──────────────────────────────────────────────────────────────
MIN_PRICE = 0.50
MAX_PRICE = 200.00
MAX_QUANTITY = 100
MIN_DAYS_USABLE = 7
MIN_DAYS_RECOMMENDED = 30
IDEAL_DAYS = 90


def _normalize(col_name):
    """Normalize a column name for matching."""
    return col_name.strip().lower().replace("_", " ").replace("-", " ")


def _try_parse_date(value):
    """Try common date formats. Returns datetime or None."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y",
                "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _try_parse_time(value):
    """Try common time formats. Returns time string or None."""
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
        try:
            datetime.strptime(value.strip(), fmt)
            return value.strip()
        except (ValueError, AttributeError):
            continue
    return None


def _try_parse_number(value):
    """Parse a number, stripping currency symbols and commas."""
    if value is None:
        return None
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if cleaned in ("", "-"):
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


# ── Main validation ─────────────────────────────────────────────────────────

class ValidationResult:
    """Collects errors, warnings, and info during validation."""

    def __init__(self):
        self.errors = []      # blockers — can't run analysis
        self.warnings = []    # problems that degrade quality
        self.info = []        # suggestions / nice-to-haves
        self.column_map = {}  # their column name -> our canonical name
        self.stats = {}       # summary stats for the report

    @property
    def is_valid(self):
        return len(self.errors) == 0

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.info.append(msg)


def validate_file(csv_path):
    """Validate a CSV file and return a ValidationResult."""
    result = ValidationResult()
    path = Path(csv_path)

    # ── File-level checks ───────────────────────────────────────────────
    if not path.exists():
        result.error(f"File not found: {path}")
        return result

    if path.suffix.lower() not in (".csv", ".tsv", ".txt"):
        result.warn(f"Unexpected file extension '{path.suffix}'. Expected .csv")

    file_size = path.stat().st_size
    if file_size == 0:
        result.error("File is empty (0 bytes)")
        return result
    if file_size > 100 * 1024 * 1024:
        result.warn(f"File is {file_size / 1024 / 1024:.0f} MB — large files may be slow to process")

    # ── Read and detect delimiter ───────────────────────────────────────
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(4096)
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as f:
                sample = f.read(4096)
            result.note("File uses Latin-1 encoding (not UTF-8) — we can handle it")
        except Exception as e:
            result.error(f"Cannot read file: {e}")
            return result

    try:
        dialect = csv.Sniffer().sniff(sample)
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    # ── Read all rows ───────────────────────────────────────────────────
    encoding = "utf-8-sig"
    try:
        with open(path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            raw_columns = reader.fieldnames or []
            rows = list(reader)
    except UnicodeDecodeError:
        encoding = "latin-1"
        with open(path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            raw_columns = reader.fieldnames or []
            rows = list(reader)

    if not raw_columns:
        result.error("No header row found. The first row should contain column names.")
        return result

    if not rows:
        result.error("File has a header row but no data rows")
        return result

    result.stats["total_rows"] = len(rows)
    result.stats["raw_columns"] = raw_columns

    # ── Column mapping ──────────────────────────────────────────────────
    column_map = {}  # raw_col -> canonical
    for raw_col in raw_columns:
        normalized = _normalize(raw_col)
        if normalized in COLUMN_ALIASES:
            canonical = COLUMN_ALIASES[normalized]
            column_map[raw_col] = canonical

    result.column_map = column_map
    mapped_canonical = set(column_map.values())

    missing_required = [c for c in REQUIRED_COLUMNS if c not in mapped_canonical]
    if missing_required:
        result.error(
            f"Missing required columns: {', '.join(missing_required)}\n"
            f"  Your columns: {', '.join(raw_columns)}\n"
            f"  We need: {', '.join(REQUIRED_COLUMNS)}\n"
            f"  Fix: Rename or add the missing columns in your CSV"
        )
        return result

    missing_optional = [c for c in OPTIONAL_COLUMNS if c not in mapped_canonical]
    if missing_optional:
        suggestions = {
            "category": "Without 'category', we can't split beverage vs pastry vs food analysis",
            "payment_method": "Without 'payment_method', we'll skip payment preference insights",
            "location": "Without 'location', we'll treat all data as one store",
        }
        for col in missing_optional:
            result.note(f"Optional column '{col}' not found. {suggestions.get(col, '')}")

    # Build a reverse map: canonical -> raw column name
    canonical_to_raw = {v: k for k, v in column_map.items()}

    # ── Per-row validation ──────────────────────────────────────────────
    date_col = canonical_to_raw["date"]
    time_col = canonical_to_raw["time"]
    item_col = canonical_to_raw["item"]
    qty_col = canonical_to_raw["quantity"]
    price_col = canonical_to_raw["price"]

    bad_dates = []
    bad_times = []
    empty_items = 0
    bad_quantities = []
    bad_prices = []
    zero_prices = 0
    negative_prices = 0
    high_prices = []
    parsed_dates = []

    for i, row in enumerate(rows, start=2):  # row 1 is header
        # Date
        date_val = row.get(date_col, "").strip()
        if not date_val:
            bad_dates.append(i)
        else:
            parsed = _try_parse_date(date_val)
            if parsed is None:
                bad_dates.append(i)
            else:
                parsed_dates.append(parsed)

        # Time
        time_val = row.get(time_col, "").strip()
        if not time_val:
            bad_times.append(i)
        elif _try_parse_time(time_val) is None:
            bad_times.append(i)

        # Item
        item_val = row.get(item_col, "").strip()
        if not item_val:
            empty_items += 1

        # Quantity
        qty = _try_parse_number(row.get(qty_col, ""))
        if qty is None:
            bad_quantities.append((i, row.get(qty_col, "")))
        elif qty <= 0:
            bad_quantities.append((i, row.get(qty_col, "")))
        elif qty > MAX_QUANTITY:
            bad_quantities.append((i, row.get(qty_col, "")))

        # Price
        price = _try_parse_number(row.get(price_col, ""))
        if price is None:
            bad_prices.append((i, row.get(price_col, "")))
        elif price == 0:
            zero_prices += 1
        elif price < 0:
            negative_prices += 1
            bad_prices.append((i, row.get(price_col, "")))
        elif price < MIN_PRICE:
            bad_prices.append((i, row.get(price_col, "")))
        elif price > MAX_PRICE:
            high_prices.append((i, price))

    total = len(rows)

    # ── Report date issues ──────────────────────────────────────────────
    if bad_dates:
        pct = len(bad_dates) / total * 100
        if pct > 50:
            example_val = rows[bad_dates[0] - 2].get(date_col, "")
            result.error(
                f"{len(bad_dates)} rows ({pct:.0f}%) have invalid/missing dates\n"
                f"  Example from row {bad_dates[0]}: '{example_val}'\n"
                f"  Expected formats: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY\n"
                f"  Fix: Check your POS export date format settings"
            )
        else:
            result.warn(
                f"{len(bad_dates)} rows ({pct:.1f}%) have invalid/missing dates "
                f"(rows: {_fmt_rows(bad_dates)})"
            )

    if bad_times:
        pct = len(bad_times) / total * 100
        if pct > 50:
            result.error(
                f"{len(bad_times)} rows ({pct:.0f}%) have invalid/missing times\n"
                f"  Expected formats: HH:MM, HH:MM:SS, H:MM AM/PM"
            )
        else:
            result.warn(
                f"{len(bad_times)} rows ({pct:.1f}%) have invalid/missing times "
                f"(rows: {_fmt_rows(bad_times)})"
            )

    # ── Report item issues ──────────────────────────────────────────────
    if empty_items:
        pct = empty_items / total * 100
        result.warn(f"{empty_items} rows ({pct:.1f}%) have empty item names")

    # ── Report quantity issues ──────────────────────────────────────────
    if bad_quantities:
        pct = len(bad_quantities) / total * 100
        examples = bad_quantities[:3]
        example_str = ", ".join(f"row {r}: '{v}'" for r, v in examples)
        if pct > 20:
            result.error(
                f"{len(bad_quantities)} rows ({pct:.0f}%) have invalid quantities\n"
                f"  Examples: {example_str}\n"
                f"  Fix: Quantities should be positive whole numbers (1, 2, 3...)"
            )
        else:
            result.warn(
                f"{len(bad_quantities)} rows ({pct:.1f}%) have invalid quantities "
                f"({example_str})"
            )

    # ── Report price issues ─────────────────────────────────────────────
    if bad_prices:
        pct = len(bad_prices) / total * 100
        examples = bad_prices[:3]
        example_str = ", ".join(f"row {r}: '{v}'" for r, v in examples)
        result.warn(
            f"{len(bad_prices)} rows ({pct:.1f}%) have invalid prices ({example_str})"
        )

    if zero_prices:
        pct = zero_prices / total * 100
        if pct > 10:
            result.warn(
                f"{zero_prices} rows ({pct:.1f}%) have $0.00 prices — "
                f"comps/voids? These will skew average ticket size"
            )
        else:
            result.note(f"{zero_prices} rows with $0.00 prices (comps/voids — minor)")

    if negative_prices:
        result.warn(
            f"{negative_prices} rows have negative prices (refunds?). "
            f"These will reduce revenue totals"
        )

    if high_prices:
        examples = high_prices[:3]
        example_str = ", ".join(f"row {r}: ${v:.2f}" for r, v in examples)
        result.warn(
            f"{len(high_prices)} rows have prices above ${MAX_PRICE:.0f} ({example_str}). "
            f"Verify these aren't data errors"
        )

    # ── Date range analysis ─────────────────────────────────────────────
    if parsed_dates:
        min_date = min(parsed_dates)
        max_date = max(parsed_dates)
        date_range_days = (max_date - min_date).days + 1
        unique_dates = len(set(d.date() for d in parsed_dates))

        result.stats["date_start"] = min_date.strftime("%Y-%m-%d")
        result.stats["date_end"] = max_date.strftime("%Y-%m-%d")
        result.stats["date_range_days"] = date_range_days
        result.stats["unique_dates"] = unique_dates

        if date_range_days < MIN_DAYS_USABLE:
            result.error(
                f"Only {date_range_days} days of data ({min_date.date()} to {max_date.date()})\n"
                f"  We need at least {MIN_DAYS_USABLE} days to produce useful insights\n"
                f"  Fix: Export a longer date range from your POS"
            )
        elif date_range_days < MIN_DAYS_RECOMMENDED:
            result.warn(
                f"{date_range_days} days of data ({min_date.date()} to {max_date.date()}). "
                f"We recommend {MIN_DAYS_RECOMMENDED}+ days for reliable patterns"
            )
        elif date_range_days < IDEAL_DAYS:
            result.note(
                f"{date_range_days} days of data — good enough to start. "
                f"{IDEAL_DAYS} days would capture seasonal patterns"
            )
        else:
            result.note(f"{date_range_days} days of data — excellent range")

        # Check for gaps (missing days)
        if unique_dates < date_range_days * 0.7:
            gap_pct = (1 - unique_dates / date_range_days) * 100
            result.warn(
                f"Only {unique_dates} unique dates in a {date_range_days}-day range "
                f"({gap_pct:.0f}% of days missing). Are there days the shop was closed, "
                f"or is the export incomplete?"
            )

    # ── Duplicate check ─────────────────────────────────────────────────
    seen = set()
    exact_dupes = 0
    for row in rows:
        key = (row.get(date_col, ""), row.get(time_col, ""),
               row.get(item_col, ""), row.get(qty_col, ""),
               row.get(price_col, ""))
        if key in seen:
            exact_dupes += 1
        seen.add(key)

    if exact_dupes:
        pct = exact_dupes / total * 100
        if pct > 20:
            result.warn(
                f"{exact_dupes} possible duplicate rows ({pct:.0f}%). "
                f"If these are separate transactions, add a transaction ID column"
            )
        elif exact_dupes > 5:
            result.note(
                f"{exact_dupes} rows look like duplicates ({pct:.1f}%) — "
                f"likely just repeated orders (same item, same time)"
            )

    # ── Summary stats ───────────────────────────────────────────────────
    result.stats["encoding"] = encoding
    result.stats["delimiter"] = repr(delimiter)
    result.stats["bad_dates"] = len(bad_dates)
    result.stats["bad_times"] = len(bad_times)
    result.stats["empty_items"] = empty_items
    result.stats["bad_quantities"] = len(bad_quantities)
    result.stats["bad_prices"] = len(bad_prices)
    result.stats["zero_prices"] = zero_prices

    return result


def _fmt_rows(row_numbers, limit=5):
    """Format a list of row numbers for display."""
    if len(row_numbers) <= limit:
        return ", ".join(str(r) for r in row_numbers)
    shown = ", ".join(str(r) for r in row_numbers[:limit])
    return f"{shown} ... and {len(row_numbers) - limit} more"


# ── Rename helper ───────────────────────────────────────────────────────────

def suggest_rename_map(result):
    """Return a dict of renames needed to match our canonical schema."""
    renames = {}
    for raw_col, canonical in result.column_map.items():
        if raw_col != canonical:
            renames[raw_col] = canonical
    return renames


# ── Report printer ──────────────────────────────────────────────────────────

def print_report(result):
    """Print a human-readable validation report."""
    stats = result.stats

    print("=" * 60)
    print("PULPIQ DATA VALIDATION REPORT")
    print("=" * 60)

    # File info
    print(f"\n  Rows:        {stats.get('total_rows', '?')}")
    print(f"  Columns:     {', '.join(stats.get('raw_columns', []))}")
    if "date_start" in stats:
        print(f"  Date range:  {stats['date_start']} to {stats['date_end']} "
              f"({stats['date_range_days']} days, {stats['unique_dates']} with sales)")

    # Column mapping
    if result.column_map:
        renames = suggest_rename_map(result)
        if renames:
            print(f"\n  Column mapping (your name -> ours):")
            for raw, canonical in renames.items():
                print(f"    '{raw}' -> '{canonical}'")
        else:
            print(f"\n  Column names match our format exactly")

    # Verdict
    if result.is_valid and not result.warnings:
        print(f"\n  RESULT: Data looks good!")
        print(f"  Ready to analyze.")
    elif result.is_valid:
        print(f"\n  RESULT: Data is usable, but has some issues")
        print(f"  We can run analysis, but fixing these will improve accuracy.")
    else:
        print(f"\n  RESULT: Issues found - cannot run analysis yet")

    # Errors
    if result.errors:
        print(f"\n  ERRORS ({len(result.errors)}):")
        for e in result.errors:
            for line in e.split("\n"):
                print(f"    {line}")
            print()

    # Warnings
    if result.warnings:
        print(f"\n  WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            for line in w.split("\n"):
                print(f"    {line}")
            print()

    # Info
    if result.info:
        print(f"\n  NOTES:")
        for n in result.info:
            print(f"    {n}")

    print(f"\n{'='*60}")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parents[2] / "data" / "sample-data" / "sample-cafe-sales.csv"
    )
    result = validate_file(csv_path)
    print_report(result)
    sys.exit(0 if result.is_valid else 1)
