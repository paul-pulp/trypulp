# START HERE: PulpIQ Self-Serve Cafe Analytics

**What PulpIQ does:** Cafe owners upload their POS sales data (CSV) and instantly see what's selling, what's wasting, and what to change. They come back weekly to track trends.

**What this codebase is:** A Flask web app that runs the analysis and shows results in the browser. No manual report generation, no email templates, no PDFs.

---

## How It Works for the Cafe Owner

```
1. Owner visits pulpiq.io → clicks "Get Started"
2. Enters email + cafe name → receives magic link (no password)
3. Clicks link → lands on dashboard
4. Uploads their POS sales CSV (drag and drop)
5. Sees instant baseline report: revenue, top items, waste analysis, milk usage
6. Comes back next week → uploads new CSV → sees week-over-week comparison
7. Repeat weekly — trends build over time
```

That's it. Fully self-serve. No manual steps on your end.

---

## What the Owner Needs to Upload

A CSV export from their POS system (Square, Toast, Clover, or any POS).

**Required columns** (5):

| What we need | Column names that auto-map |
|---|---|
| **Date** | `date`, `Sale Date`, `Transaction Date`, `Order Date` |
| **Time** | `time`, `Sale Time`, `Transaction Time`, `Order Time` |
| **Item name** | `item`, `Item Name`, `Product`, `Menu Item`, `Description` |
| **Quantity** | `quantity`, `Qty`, `Units`, `Count`, `Units Sold` |
| **Price** | `price`, `Total`, `Amount`, `Sale Amount`, `Revenue`, `Net Sales` |

**Optional but makes it better** (3):

| What it adds | Column names that auto-map |
|---|---|
| **Category** (beverage/pastry/food split) | `category`, `Type`, `Item Category` |
| **Payment method** | `payment_method`, `Payment Method`, `Payment Type` |
| **Location** (multi-store) | `location`, `Store`, `Store Name` |

Capitalization doesn't matter. The validator auto-maps 40+ POS column name variations.

**How much data:**
- 7 days minimum (rough estimates)
- 30 days recommended (captures weekly patterns)
- 90 days ideal (captures seasonal trends)

---

## What the Owner Sees in Their Report

### Revenue & Product Intelligence
- Average daily revenue, ticket size, transactions
- Top 10 items by revenue (with % of total)
- Revenue breakdown by category (beverage vs food vs pastry)
- Payment method preferences (credit vs cash, avg ticket by method)
- Hot vs iced drink patterns (and when iced spikes)
- Time-of-day preferences (what sells at 7am vs 2pm)
- Add-on detection (oat milk, almond milk, mocha from item names)

### Waste Analysis
- Perishable sell-through rates (% of days each item actually sold)
- Slow-moving items flagged by waste risk (HIGH / MEDIUM / LOW)
- Order quantity recommendations ("order 5 instead of 9")
- Waste projection in dollars per month
- Day-of-week ordering patterns ("order more croissants on Saturday")
- Milk usage by type (dairy, oat, almond) with ordering recommendations

### Week-Over-Week Comparison (2nd upload onward)
- Revenue change vs previous week
- Ticket size change
- Transaction volume change
- Waste reduction progress
- Green/red delta indicators for each metric

---

## Running the App Locally

### Prerequisites

- Python 3.10+
- Node.js (for Tailwind CSS build)

### Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Build CSS (from src/webapp/)
cd src/webapp
npm install
npm run build:css
cd ../..

# Run the dev server
python wsgi.py
```

The app runs at **http://localhost:5000**.

In dev mode, magic links print to the terminal instead of sending emails. Copy the link and paste it in your browser to log in.

### For production

Set these environment variables:
```
SECRET_KEY=<random-secret-for-sessions>
SMTP_USER=<gmail-address>
SMTP_PASS=<gmail-app-password>
APP_URL=https://app.pulpiq.io
DATABASE_PATH=/data/pulpiq.db
```

---

## Project Structure

```
pulpiq-project/
  src/
    analysis/                     # Analysis engine (Python/pandas)
      customer_intelligence.py    # Revenue, top items, categories, trends
      waste_analysis.py           # Perishable waste, milk usage, order recs
      validate_data.py            # CSV validation + column mapping
      product_classifier.py       # Auto-classify items/categories, cost defaults

    webapp/                       # Flask web app
      __init__.py                 # App factory
      config.py                   # Settings (from env vars)
      models.py                   # SQLite database (users, tokens, snapshots)
      auth.py                     # Magic link authentication
      analysis_runner.py          # Glue: calls analysis modules, serializes results
      views/
        auth_views.py             # /login, /verify, /logout
        upload_views.py           # /upload → validate → analyze → store
        dashboard_views.py        # /dashboard, /report, /compare
      templates/                  # Jinja2 HTML templates
      static/                    # Compiled Tailwind CSS

    website/                      # Landing page (static, hosted on Netlify)
      index.html
      success.html

  data/                           # Test data (not deployed)
  wsgi.py                         # WSGI entry point
  requirements.txt                # Python dependencies
```

---

## Cost Defaults

All costs are **Toronto, Canada (CAD)** industry averages. These are used when calculating waste costs and savings estimates.

Source: Sysco/Saputo foodservice pricing, Oatly/Pacific wholesale case pricing, Statistics Canada, Ontario ESA (2025-2026).

| Item | Cost | Source |
|------|------|--------|
| Dairy milk | $0.04/oz (~$5.10/gal) | Saputo via foodservice distributor |
| Oat milk | $0.15/oz (~$4.50/946mL) | Oatly Barista case price |
| Almond milk | $0.14/oz (~$4.62/946mL) | Pacific Barista case price |
| Soy milk | $0.12/oz (~$3.83/946mL) | Pacific Barista case price |
| Coconut milk | $0.15/oz (~$4.75/946mL) | Pacific Barista case price |
| Perishable COGS | 30% of menu price | Industry avg, beverage-heavy cafe |

These live in `src/analysis/product_classifier.py` → `DEFAULT_COSTS` dict.

---

## How the Analysis Works (Under the Hood)

### When a CSV is uploaded:

1. **Validate** (`validate_data.py`) — maps column names, checks data quality, flags issues
2. **Classify products** (`product_classifier.py`) — auto-detects beverages vs perishable food from category names and item names using keyword matching
3. **Customer intelligence** (`customer_intelligence.py`) — revenue, top items, categories, payment methods, hourly/daily trends, hot vs iced, add-ons
4. **Waste analysis** (`waste_analysis.py`) — sell-through rates, slow movers, milk usage by type, order recommendations, waste projections, day-of-week patterns
5. **Serialize** (`analysis_runner.py`) — converts pandas DataFrames to JSON for storage
6. **Store** — flat metrics + full JSON blobs saved to SQLite
7. **Compare** — if this isn't the first upload, calculates deltas vs previous week

Processing time: ~2-5 seconds for a typical 5,000-row cafe CSV.

### What auto-adapts:
- Column names (40+ POS variations mapped automatically)
- Product categories (keyword detection — works with "Pastry", "Bakery", "Baked Goods", "Pizza", etc.)
- Milk types (detects dairy, oat, almond, soy, coconut from item names like "Oat Milk Latte")
- Time formats (HH:MM, HH:MM:SS, mixed)
- Date formats (YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, etc.)

---

## Deployment

**Recommended:** Railway.app ($5/month)
- Supports Python out of the box
- SQLite works on persistent volume
- `git push` deploys
- Free SSL

**Landing page:** stays on Netlify (already configured)

**Architecture:**
- `pulpiq.io` → Netlify (landing page)
- `app.pulpiq.io` → Railway (Flask app)
