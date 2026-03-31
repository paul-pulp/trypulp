"""
Analysis Runner — glue between Flask and the existing analysis modules.
Calls customer_intelligence and waste_analysis, serializes pandas output to JSON-safe dicts.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

# Add the analysis directory to sys.path so its internal imports work
_ANALYSIS_DIR = str(Path(__file__).resolve().parent.parent / "analysis")
if _ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, _ANALYSIS_DIR)

import csv
import tempfile

from validate_data import validate_file
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
