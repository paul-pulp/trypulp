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


def run_analysis(csv_path):
    """Run validation + analysis on a CSV file.

    Returns:
        {
            "customer": dict,     # customer_intelligence results (serialized)
            "waste": dict,        # waste_analysis results (serialized)
            "errors": list[str],  # validation errors (empty if OK)
            "warnings": list[str],
        }
    """
    # Step 1: Validate
    validation = validate_file(csv_path)

    # Hard errors block analysis
    if not validation.is_valid:
        date_range_errors = [e for e in validation.errors if "days of data" in e]
        hard_errors = [e for e in validation.errors if e not in date_range_errors]
        if hard_errors:
            return {
                "customer": {},
                "waste": {},
                "errors": hard_errors,
                "warnings": validation.warnings,
            }

    # Step 2: Run analysis modules
    customer = run_customer(csv_path)
    waste = run_waste(csv_path)

    return {
        "customer": customer,
        "waste": waste,
        "errors": [],
        "warnings": validation.warnings,
    }
