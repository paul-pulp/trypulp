# START HERE: PulpIQ — Product Owner Guide

## What PulpIQ Is

PulpIQ is a self-serve analytics tool for cafe owners. They upload their POS sales data (a CSV file) and instantly see:

- **What's selling** — top items, revenue by category, payment preferences, time-of-day trends
- **What's wasting** — perishable items going unsold, milk over-ordering, ordering recommendations
- **What's changing** — week-over-week comparison of revenue, ticket size, and waste

No onboarding calls, no manual reports, no PDFs. The cafe owner does everything themselves through the web app.

---

## The Customer Journey

```
1. Cafe owner visits pulpiq.io (landing page on Netlify)
2. Clicks "Get Started" → goes to trypulp.onrender.com/login
3. Enters email + cafe name → receives magic link email (no password)
4. Clicks magic link → lands on their dashboard
5. Clicks "Upload Data" → drags in their POS CSV
6. Sees instant baseline report (2-5 seconds processing)
7. Next week → logs in again → uploads new week's CSV
8. Sees week-over-week comparison (revenue up/down, waste improving, etc.)
9. Repeats weekly — trends build over time
```

**You don't do anything.** The whole flow is automated.

---

## What the Owner Uploads

A CSV export from their POS (Square, Toast, Clover, or any system). The app auto-detects 40+ column name variations, so it works with almost any POS export.

**Required:** Date, Time, Item Name, Quantity, Price/Total

**Optional but better:** Category, Payment Method, Location

**Data range:** 7 days minimum. 30 days recommended. 90 days ideal.

---

## What the Owner Sees

### Baseline Report (first upload)

| Section | What it shows |
|---------|--------------|
| **Summary cards** | Daily revenue, avg ticket, transactions, menu item count |
| **What's Selling** | Top 10 items by revenue with % of total and inline bars |
| **Your Product Mix** | Revenue by category (Beverage/Food/Pastry) with progress bars |
| **How They Pay** | Credit vs cash split, avg ticket per method |
| **Where You're Losing Money** | Daily waste items, monthly waste cost, savings potential |
| **Waste table** | Per-item: avg sold/day, estimated current order, recommended order, wasted/month |
| **Your Milk Breakdown** | Usage by type (dairy, oat, almond), ordering recommendations |

Every metric has a **tooltip** (hover the ? icon) explaining exactly how it's calculated.

### Weekly Comparison (second upload onward)

- Revenue, ticket, and transaction changes with $ and % deltas
- Waste unit and cost changes (green = improving, red = getting worse)
- Headline callout ("Revenue is up 4.7% this week")

### Dashboard

- Latest metrics with change indicators
- Full upload history with links to each report and comparison

---

## How the Analysis Actually Works

When a CSV is uploaded, here's what happens in ~2-5 seconds:

### Step 1: Validate (`validate_data.py`)
Maps whatever column names the POS uses to our standard names. Checks dates, prices, quantities are valid. Flags warnings (short data range, $0 prices, duplicates). Blocks if critical columns are missing.

### Step 2: Classify Products (`product_classifier.py`)
Auto-detects what each item is using keyword matching:
- **Beverages:** anything with "latte", "cappuccino", "cold brew", "tea", "smoothie", etc.
- **Perishable food:** anything with "croissant", "muffin", "sandwich", "pizza", etc.
- **Milk type:** detects "oat", "almond", "soy", "coconut" from item names

This means the app works with any cafe menu — no manual configuration.

### Step 3: Customer Intelligence (`customer_intelligence.py`)
Calculates: top items by revenue, revenue by category, payment methods, daily trends (best/worst day), hourly trends (peak hour), hot vs iced patterns, time-of-day preferences, add-on detection.

### Step 4: Waste Analysis (`waste_analysis.py`)
Calculates:
- **Sell-through rates** — what % of days each perishable item actually sold
- **Order recommendations** — avg daily sales + small buffer (replaces guessed peak ordering)
- **Waste projection** — (current estimated order - avg sold) × ingredient cost × 30 days
- **Milk usage** — oz/day by type, gallon/carton recommendations
- **Day-of-week patterns** — which items sell more on specific days
- **Savings** — how much they'd save by switching to recommended quantities

### Step 5: Store Results
Flat metrics saved to SQLite for quick dashboard queries. Full analysis JSON blobs saved for rendering detailed reports.

### Step 6: Compare (if not first upload)
Calculates deltas between this upload and the previous one — revenue change, ticket change, waste change.

---

## How Savings Are Calculated

This is the number cafe owners care about most. Here's exactly how it works:

### Perishable Waste Savings
```
For each perishable item:
  current_estimated_order = the max quantity sold on any single day
    (cafes tend to order for their busiest day)
  recommended_order = average daily sales + half a standard deviation
    (covers most days without over-ordering)
  daily_waste = current_estimated_order - average_daily_sales
  ingredient_cost = item's avg menu price × 30% COGS ratio
  monthly_waste = daily_waste × ingredient_cost × 30 days

  savings = current_monthly_waste - optimized_monthly_waste
```

### Milk Waste Savings
```
  daily_milk_cost = sum of (daily oz per type × cost per oz)
  assumed_waste = 10% of daily milk cost (industry average over-ordering)
  savings = 60% of that waste (realistic reduction target)
  monthly_milk_savings = daily savings × 30 days
```

### Total Savings
```
  total = perishable_savings + milk_savings
  capped at 15% of monthly revenue (prevents unrealistic claims)
```

### Cost Assumptions (Toronto CAD)

| Item | Cost | Source |
|------|------|--------|
| Dairy milk | $0.04/oz (~$5.10/gal) | Saputo via foodservice distributor |
| Oat milk | $0.15/oz (~$4.50/946mL) | Oatly Barista case price |
| Almond milk | $0.14/oz (~$4.62/946mL) | Pacific Barista case price |
| Soy milk | $0.12/oz (~$3.83/946mL) | Pacific Barista case price |
| Coconut milk | $0.15/oz (~$4.75/946mL) | Pacific Barista case price |
| Perishable COGS | 30% of menu price | Industry avg, beverage-heavy cafe |

These live in `src/analysis/product_classifier.py` → `DEFAULT_COSTS`. To change them, edit that file and redeploy.

---

## Infrastructure

### Where things live

| What | Where | URL |
|------|-------|-----|
| Landing page | Netlify | pulpiq.io |
| Web app | Render.com | trypulp.onrender.com |
| Database | SQLite on Render persistent disk | /opt/render/project/data/pulpiq.db |
| Code | GitHub | github.com/paul-pulp/trypulp |

### How deploys work

Push to `main` on GitHub → Render auto-deploys in ~2 minutes. No manual steps.

```bash
git add -A && git commit -m "description" && git push origin main
```

### Environment variables (Render dashboard → Environment tab)

| Variable | What it does | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Signs session cookies | (auto-generated by Render) |
| `DATABASE_PATH` | Where SQLite lives | `/opt/render/project/data/pulpiq.db` |
| `APP_URL` | Used in magic link emails | `https://trypulp.onrender.com` |
| `SMTP_USER` | Gmail address for sending | `paul@pulpiq.io` |
| `SMTP_PASS` | Gmail app password | (from myaccount.google.com/apppasswords) |
| `BACKUP_KEY` | Secret URL segment for manual backup | `my-secret-key-2026` |

---

## Database Backups

### Automatic (daily)
A background thread runs every 24 hours. It:
1. Copies the SQLite database using `sqlite3.backup()` (safe, handles write-ahead log)
2. Saves to `/opt/render/project/data/backups/` with a timestamp
3. Emails the backup file to your `SMTP_USER` address as an attachment
4. Keeps the last 7 backups on disk, auto-deletes older ones

You'll receive an email like:
```
Subject: PulpIQ Database Backup — 2026-03-29 14:00 UTC
Attachment: pulpiq-backup-2026-03-29_140000.db (12.4 KB)
```

### Manual trigger
Hit this URL in your browser (replace YOUR_KEY with your `BACKUP_KEY`):
```
https://trypulp.onrender.com/admin/backup/YOUR_KEY
```

Returns JSON: `{"status": "ok", "file": "pulpiq-backup-2026-03-29_153000.db"}`

### Restoring from a backup

If something goes wrong and you need to restore:

1. Download the `.db` file from your email
2. Open a Render shell (Dashboard → your service → Shell tab)
3. Stop the app, replace the database, restart:
```bash
# In Render shell:
cp /opt/render/project/data/pulpiq.db /opt/render/project/data/pulpiq-pre-restore.db
# Upload the backup .db file (via Render's file upload or scp)
cp pulpiq-backup-2026-03-29_140000.db /opt/render/project/data/pulpiq.db
```
4. Trigger a manual deploy from the Render dashboard to restart the app

### What's in the database

3 tables:
- **users** — email, cafe name, created date
- **auth_tokens** — magic link tokens (expire after 15 min)
- **snapshots** — every upload's analysis results (flat metrics + full JSON blobs)

---

## Troubleshooting

### "502 Bad Gateway" on Render
- Check the **Logs** tab in Render dashboard
- Most likely: the app crashed on startup (missing env var, import error)
- Fix: push a fix to GitHub, Render auto-redeploys

### Magic link emails not arriving
1. Check Render logs for `[AUTH]` lines — they show exactly what happened
2. `SMTP_USER configured: no` → env var not set in Render
3. `Email send FAILED: ...` → wrong password, or Gmail blocked it
4. The magic link always prints in the logs as a fallback — you can copy it from there

### Cafe owner uploads CSV and gets errors
- The validator gives specific error messages ("Missing required columns: time")
- Common fix: ask them to re-export with the right columns
- The app handles 40+ column name variations automatically — if it still fails, the POS export is probably missing a required field

### Analysis seems wrong
- Check the CSV data quality (weird items, $0 prices, very short date range)
- Savings are capped at 15% of monthly revenue — if they seem low, that cap may be binding
- Cost defaults are Toronto averages — if the cafe is elsewhere or pays very different prices, the dollar amounts will be off (the ordering recommendations are still correct since they're based on sales volume, not costs)

### Render persistent disk full
- The SQLite database is tiny (KB to a few MB)
- Backups auto-clean to last 7 files
- If somehow full: delete old backups via Render shell
- The disk is 1GB — you'd need thousands of cafes before this matters

### Need to reset a user's data
```sql
-- In Render shell, run:
sqlite3 /opt/render/project/data/pulpiq.db
-- Delete all snapshots for a user:
DELETE FROM snapshots WHERE user_id = (SELECT id FROM users WHERE email = 'owner@cafe.com');
-- Or delete the user entirely:
DELETE FROM snapshots WHERE user_id = (SELECT id FROM users WHERE email = 'owner@cafe.com');
DELETE FROM auth_tokens WHERE user_id = (SELECT id FROM users WHERE email = 'owner@cafe.com');
DELETE FROM users WHERE email = 'owner@cafe.com';
```

---

## Running Locally for Development

```bash
# Install Python deps
pip install -r requirements.txt

# Build CSS (only needed after template changes)
cd src/webapp && npm install && npm run build:css && cd ../..

# Run dev server
python wsgi.py
```

App runs at **http://localhost:5000**. Magic links print to the terminal (no emails in dev mode).

### Watching CSS changes during development
```bash
cd src/webapp && npm run watch:css
```

This auto-rebuilds `styles.css` when you edit templates or `input.css`.

---

## Project Structure

```
src/
  analysis/                     # Analysis engine (pure Python, no Flask dependency)
    customer_intelligence.py    # Revenue, top items, categories, trends
    waste_analysis.py           # Perishable waste, milk usage, order recs
    validate_data.py            # CSV validation + column mapping
    product_classifier.py       # Auto-classify items, cost defaults (Toronto CAD)

  webapp/                       # Flask web app
    __init__.py                 # App factory, context processor, backup scheduler
    models.py                   # SQLite: users, tokens, snapshots
    auth.py                     # Magic link generation + email sending
    backup.py                   # Database backup + email delivery
    analysis_runner.py          # Calls analysis modules, serializes pandas → JSON
    views/
      auth_views.py             # /login, /verify, /logout
      upload_views.py           # /upload → validate → analyze → store → redirect
      dashboard_views.py        # /dashboard, /report/<id>, /compare/<id>
    templates/                  # Jinja2 HTML (Tailwind CSS)
    static/
      input.css                 # Tailwind source (custom theme, animations, tooltips)
      styles.css                # Compiled CSS (committed, no build step on deploy)

  website/                      # Landing page (Netlify, separate from the app)

wsgi.py                         # Entry point: python wsgi.py or gunicorn wsgi:app
requirements.txt                # Python dependencies
render.yaml                     # Render deployment config
```
