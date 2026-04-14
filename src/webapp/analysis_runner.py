"""
Analysis Runner — glue between Flask and the existing analysis modules.
Calls customer_intelligence and waste_analysis, serializes pandas output to JSON-safe dicts.
"""

import sys
import json as _json
from pathlib import Path

import pandas as pd
import numpy as np

# Add the analysis directory to sys.path so its internal imports work
_ANALYSIS_DIR = str(Path(__file__).resolve().parent.parent / "analysis")
if _ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, _ANALYSIS_DIR)

import csv
import tempfile

from validate_data import validate_file, COLUMN_ALIASES, _normalize
from customer_intelligence import run as run_customer
from waste_analysis import run as run_waste


def serialize_results(obj):
    """Recursively convert pandas/numpy types to JSON-safe Python types."""
    if isinstance(obj, pd.DataFrame):
        return obj.reset_index().to_dict(orient="records")
    if isinstance(obj, pd.Series):
        return obj.to_dict()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return round(float(obj), 4)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {str(k): serialize_results(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serialize_results(i) for i in obj]
    if pd.isna(obj) if isinstance(obj, float) else False:
        return None
    return obj


def _write_cleaned_csv(original_path, column_map):
    """Write a cleaned CSV with auto-fixed columns renamed to canonical names."""
    # Read original
    try:
        with open(original_path, "r", encoding="utf-8-sig") as f:
            sample = f.read(4096)
        try:
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
        with open(original_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)
    except UnicodeDecodeError:
        with open(original_path, "r", encoding="latin-1") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)

    # Build canonical fieldnames
    canonical_fields = []
    raw_to_canonical = {}
    for raw_col, canonical in column_map.items():
        if canonical not in canonical_fields:
            canonical_fields.append(canonical)
            raw_to_canonical[raw_col] = canonical

    # Write cleaned CSV
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w",
                                      newline="", encoding="utf-8")
    writer = csv.DictWriter(tmp, fieldnames=canonical_fields)
    writer.writeheader()
    for row in rows:
        clean_row = {}
        for raw_col, canonical in raw_to_canonical.items():
            clean_row[canonical] = row.get(raw_col, "")
        writer.writerow(clean_row)
    tmp.close()
    return tmp.name


# ── AI column mapping with token management ──────────────────────────────────

# In-memory cache: frozenset of header names → column_map dict
# Avoids repeat API calls when the same POS format is uploaded multiple times.
_ai_cache = {}

# Simple monthly token counter (resets on month change)
_token_usage = {"month": None, "input": 0, "output": 0, "calls": 0}

# Default cap: 50,000 input tokens/month (~$0.01 on Haiku, ~250 uploads)
AI_MONTHLY_TOKEN_CAP = 50_000


def _check_token_budget():
    """Return True if we're within the monthly token budget."""
    from datetime import datetime
    current_month = datetime.utcnow().strftime("%Y-%m")
    if _token_usage["month"] != current_month:
        # New month — reset counters
        _token_usage["month"] = current_month
        _token_usage["input"] = 0
        _token_usage["output"] = 0
        _token_usage["calls"] = 0
    return _token_usage["input"] < AI_MONTHLY_TOKEN_CAP


def _record_token_usage(response):
    """Record input/output tokens from an API response."""
    usage = getattr(response, "usage", None)
    if usage:
        _token_usage["input"] += getattr(usage, "input_tokens", 0)
        _token_usage["output"] += getattr(usage, "output_tokens", 0)
        _token_usage["calls"] += 1
        print(
            f"[AI-MAP] Tokens this call: {getattr(usage, 'input_tokens', 0)} in / "
            f"{getattr(usage, 'output_tokens', 0)} out | "
            f"Month total: {_token_usage['input']} in / {_token_usage['output']} out / "
            f"{_token_usage['calls']} calls",
            flush=True,
        )


def get_ai_usage_stats():
    """Return current month's AI token usage (for admin visibility)."""
    return dict(_token_usage)


def _ai_map_columns(csv_path):
    """Use Claude API to map unrecognized CSV columns. Returns column_map dict or None."""
    try:
        from flask import current_app
        api_key = current_app.config.get("ANTHROPIC_API_KEY", "")
    except RuntimeError:
        api_key = ""

    if not api_key:
        print("[AI-MAP] No ANTHROPIC_API_KEY — skipping AI column mapping", flush=True)
        return None

    # Read headers + first 3 rows
    try:
        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                sample = f.read(4096)
        except UnicodeDecodeError:
            with open(csv_path, "r", encoding="latin-1") as f:
                sample = f.read(4096)

        try:
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        try:
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames or []
                sample_rows = []
                for i, row in enumerate(reader):
                    sample_rows.append(dict(row))
                    if i >= 2:
                        break
        except UnicodeDecodeError:
            with open(csv_path, "r", encoding="latin-1") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames or []
                sample_rows = []
                for i, row in enumerate(reader):
                    sample_rows.append(dict(row))
                    if i >= 2:
                        break

        if not headers:
            return None
    except Exception as e:
        print(f"[AI-MAP] Failed to read CSV for AI mapping: {e}", flush=True)
        return None

    # Check cache — same header set means same POS format, reuse the mapping
    cache_key = frozenset(h.strip().lower() for h in headers)
    if cache_key in _ai_cache:
        print(f"[AI-MAP] Cache hit — reusing mapping for {len(headers)} columns", flush=True)
        return _ai_cache[cache_key]

    # Check monthly token budget
    if not _check_token_budget():
        print(
            f"[AI-MAP] Monthly token cap reached ({_token_usage['input']}/{AI_MONTHLY_TOKEN_CAP}) "
            f"— skipping AI call",
            flush=True,
        )
        return None

    prompt = (
        "You are a CSV column mapper for cafe POS systems.\n"
        "Given these column headers and sample rows, map each column to exactly one of:\n"
        "date, time, datetime, item, quantity, price, category, payment_method, location, transaction_id, skip\n\n"
        "Rules:\n"
        '- "price" = the line-item total or sale amount (NOT unit price, tax, tip, or discount)\n'
        '- "skip" = columns not useful for sales analysis (tax, tip, discount, server name, etc.)\n'
        "- Every column must be mapped to exactly one value\n\n"
        f"Headers: {headers}\n"
    )
    for i, row in enumerate(sample_rows):
        vals = [row.get(h, "") for h in headers]
        prompt += f"Row {i + 1}: {vals}\n"
    prompt += "\nRespond with ONLY a JSON object mapping column names to canonical names. No explanation."

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        # Track token usage
        _record_token_usage(response)

        text = response.content[0].text.strip()
        # Extract JSON (handle markdown code blocks)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        mapping = _json.loads(text)

        # Validate: only accept known canonical names
        valid_names = {"date", "time", "datetime", "item", "quantity", "price",
                       "category", "payment_method", "location", "transaction_id", "skip"}
        column_map = {}
        for col, canonical in mapping.items():
            canonical = canonical.strip().lower()
            if canonical in valid_names and canonical != "skip":
                column_map[col] = canonical

        print(f"[AI-MAP] AI mapped {len(column_map)} columns: {column_map}", flush=True)

        # Cache the result for this header format
        if column_map:
            _ai_cache[cache_key] = column_map

        return column_map if column_map else None

    except Exception as e:
        print(f"[AI-MAP] AI column mapping failed: {e}", flush=True)
        return None


def _is_column_mapping_error(errors):
    """Check if validation errors are about missing columns (vs empty file etc)."""
    for err in errors:
        if "price" in err.lower() and "column" in err.lower():
            return True
    return False


def run_analysis(csv_path, cost_overrides=None):
    """Run validation + analysis on a CSV file.

    Returns:
        {
            "customer": dict,     # customer_intelligence results (serialized)
            "waste": dict,        # waste_analysis results (serialized)
            "errors": list[str],  # validation errors (empty if OK)
            "warnings": list[str],
        }
    """
    # Step 1: Validate (with auto-fixes)
    validation = validate_file(csv_path)

    # Only block on truly unrecoverable errors (empty file, unreadable, no price column)
    if not validation.is_valid:
        # If it's a column mapping issue, try AI fallback
        if _is_column_mapping_error(validation.errors):
            ai_map = _ai_map_columns(csv_path)
            if ai_map:
                # Re-run validation with AI-provided column names injected as aliases
                for col_name, canonical in ai_map.items():
                    normalized = _normalize(col_name)
                    if normalized not in COLUMN_ALIASES:
                        COLUMN_ALIASES[normalized] = canonical
                validation = validate_file(csv_path)

        if not validation.is_valid:
            # Improve error message with the actual columns found
            raw_cols = validation.stats.get("raw_columns", [])
            if raw_cols:
                friendly_error = (
                    f"We found these columns in your file: {', '.join(raw_cols)}.\n"
                    f"We need a column with sale amounts (like 'Total', 'Net Sales', 'Price').\n"
                    f"If your file uses a different name, email hello@trypulp.co and we'll add support for your POS system."
                )
                validation.errors = [friendly_error]

            return {
                "customer": {},
                "waste": {},
                "errors": validation.errors,
                "warnings": validation.warnings,
            }

    # Step 1b: Write cleaned CSV if auto-fixes were applied
    analysis_path = csv_path
    if any("_auto_" in k for k in validation.column_map):
        analysis_path = _write_cleaned_csv(csv_path, validation.column_map)

    # Step 2: Run analysis modules (with user's actual costs if provided)
    customer = run_customer(analysis_path)
    waste = run_waste(analysis_path, cost_overrides)

    # Clean up temp file if we created one
    if analysis_path != csv_path:
        try:
            import os
            os.unlink(analysis_path)
        except OSError:
            pass

    return {
        "customer": customer,
        "waste": waste,
        "errors": [],
        "warnings": validation.warnings,
    }
