# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**PulpIQ** is a self-serve analytics web app for cafe owners. They upload POS sales CSVs and instantly see revenue insights, product trends, and waste analysis. They return weekly to track changes.

## Tech Stack

- **Backend:** Flask (Python) with SQLite
- **Frontend:** Jinja2 templates + Tailwind CSS (compiled via CLI, not CDN)
- **Analysis:** pandas/numpy modules in `src/analysis/`
- **Auth:** Email magic links (no passwords)
- **Costs:** Toronto, Canada (CAD) industry defaults in `product_classifier.py`

## Directory Structure

```
src/
  analysis/                     # Analysis engine (reusable Python modules)
    customer_intelligence.py    # Revenue, top items, categories, trends
    waste_analysis.py           # Perishable waste, milk usage, order recs
    validate_data.py            # CSV validation + column mapping
    product_classifier.py       # Auto-classify items, cost defaults
  webapp/                       # Flask web app
    views/                      # Route handlers (auth, upload, dashboard)
    templates/                  # Jinja2 HTML templates
    static/                     # Compiled CSS
    analysis_runner.py          # Glue between Flask and analysis modules
    models.py                   # SQLite database operations
    auth.py                     # Magic link authentication
  website/                      # Static landing page (Netlify)
docs/
  marketing/                    # Landing page copy
  research/                     # Market research, competitive analysis
  technical/                    # Tech stack decisions
data/                           # Test CSV data (not deployed)
```

## Development Commands

```bash
# Run the Flask dev server
python wsgi.py

# Build Tailwind CSS (from src/webapp/)
cd src/webapp && npm run build:css

# Watch CSS during development
cd src/webapp && npm run watch:css

# Install Python deps
pip install -r requirements.txt
```

## Key Architecture Decisions

- Analysis modules (`src/analysis/`) have NO Flask dependency — they take a CSV path and return dicts. The webapp calls them via `analysis_runner.py`.
- The analysis modules use `from product_classifier import ...` style imports. `analysis_runner.py` adds `src/analysis/` to `sys.path` to make this work.
- Tailwind CSS is compiled locally (not CDN). Run `npm run build:css` after template changes.
- SQLite stores flattened metrics (for quick queries) plus full JSON blobs (for rendering reports).
- No labor/staffing analysis — the product focuses on sales + waste only.
