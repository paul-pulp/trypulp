# PulpIQ — Product Owner Guide

## The Business

PulpIQ is a free, self-serve analytics tool for independent cafe owners. They upload their POS sales data (a CSV file) and instantly see what's selling, what's wasting money, and exactly what to change. They come back weekly to track their progress.

**The value proposition:** Most indie cafes waste $500–1,500/month on over-ordering perishables and don't have time to dig through spreadsheets. PulpIQ does the analysis in seconds.

**The business model:** Free baseline report (the hook — shows them their waste number). Weekly tracking is the paid feature ($29–49/month, not yet implemented). Once they're checking their numbers every Monday, it's hard to cancel.

**Target market:** Independent cafes in Toronto, Canada. Any size, any POS system (Square, Toast, Clover, or anything that exports CSV).

---

## What We Do for the Cafe Owner

### First Visit (Free)
1. Owner lands on **trypulp.co** — sees the landing page explaining the product
2. Clicks "Get My Free Report" → enters email + cafe name
3. Receives a magic link email (no password) with an **onboarding PDF** attached (POS export instructions for Square, Toast, Clover)
4. Clicks the magic link → lands directly on the **upload page** (not an empty dashboard)
5. Drags in their CSV → sees instant results in 2-5 seconds

### What They See in Their Report
- **Key Findings** — 3 plain-English bullets at the top ("Your biggest revenue driver is X. You're wasting $Y/month. Reducing Z could save $W/month.")
- **All Items** — every product with category filtering (Beverage / Food / Pastry pills with counts), revenue, % of total, units sold
- **Your Product Mix** — revenue by category with progress bars
- **Revenue by Day of Week** — best/worst days with inline bars
- **Revenue by Hour** — when money comes in
- **How They Pay** — credit vs cash, avg ticket per method
- **Hot vs Iced** — drink temperature split
- **Where You're Losing Money** — daily waste items, monthly waste cost, savings potential (with tooltips explaining every calculation)
- **Waste Table** — per-item: avg sold/day, estimated current order, recommended order, wasted/month
- **Your Milk Breakdown** — dairy/oat/almond usage and ordering recommendations
- **Insight callouts** — "Biggest opportunity: reduce X orders from Y to Z/day — saves $W/month"
- **Print button** for sharing with partners

### Weekly Return (Future Paid Feature)
1. Owner logs in → uploads new week's CSV
2. Sees **week-over-week comparison** with:
   - Every metric shows **vs last week** AND **vs baseline** (total progress since day one)
   - **Cumulative savings tracker** — "You've saved an estimated $X since joining PulpIQ"
   - **Biggest movers** — top 4 items that changed most this week (up/down arrows, % change)
   - **Your Focus This Week** — 2-3 specific action items that change based on the data (waste reduction, revenue insight, baseline progress)
3. Dashboard shows upload history with all past reports

### What Auto-Adapts (No Configuration Needed)
- Column names — 40+ POS variations mapped automatically
- Product categories — keyword detection works with any menu
- Milk types — detects dairy, oat, almond, soy, coconut from item names
- Time formats — HH:MM, HH:MM:SS, mixed
- Date formats — YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, etc.

---

## The Tech Stack

| Tool | What It Does | Cost |
|------|-------------|------|
| **Flask** (Python) | The web app — serves pages, runs analysis, handles auth | Free (open source) |
| **SQLite** | Database — stores users, uploads, analysis results | Free (file on disk) |
| **Tailwind CSS** | Styling — compiled locally via CLI, not CDN | Free (open source) |
| **Render.com** | Hosts the Flask app + persistent disk for the database | Free tier (or $7/mo for always-on) |
| **GitHub** | Code repository — push to deploy | Free |
| **Gmail SMTP** | Sends magic link emails and onboarding PDFs | Free (existing Google Workspace) |
| **GoDaddy** | Domain registrar for trypulp.co | ~$15/year |
| **pandas/numpy** | Python libraries that power the analysis engine | Free (open source) |
| **reportlab** | Generates the onboarding PDF attached to welcome emails | Free (open source) |

---

## Where Everything Lives

| What | Where | URL |
|------|-------|-----|
| Live site | Render.com | **trypulp.co** |
| Code | GitHub | github.com/paul-pulp/trypulp |
| Database | SQLite on Render persistent disk | /opt/render/project/data/pulpiq.db |
| Domain | GoDaddy | trypulp.co |
| DNS | GoDaddy → Render | A record: 216.24.57.1, CNAME www: trypulp.onrender.com |

---

## How Deploys Work

Push to `main` on GitHub → Render auto-deploys in ~2 minutes.

```bash
git add -A && git commit -m "description" && git push origin main
```

That's it. No build step needed — the compiled CSS is committed to the repo.

---

## Environment Variables (Render Dashboard → Environment Tab)

| Variable | What It Does | Value |
|----------|-------------|-------|
| `SECRET_KEY` | Signs session cookies | (auto-generated by Render) |
| `DATABASE_PATH` | Where SQLite lives | `/opt/render/project/data/pulpiq.db` |
| `APP_URL` | Used in magic link emails | `https://trypulp.co` |
| `SMTP_USER` | Gmail address for sending emails | your Gmail |
| `SMTP_PASS` | Gmail app password (not regular password) | from myaccount.google.com/apppasswords |
| `ADMIN_USER` | Username for admin panel | your choice |
| `ADMIN_PASS` | Password for admin panel | your choice |

**Render also needs a persistent disk:**
- Name: `pulpiq-data`
- Mount path: `/opt/render/project/data`
- Size: 1 GB

Without the disk, the database gets wiped on every deploy.

---

## Admin Panel

Access at **trypulp.co/admin/users** — browser prompts for username/password (HTTP Basic Auth using `ADMIN_USER` / `ADMIN_PASS` env vars).

### What You See

**User list** (sorted by highest savings potential):
- Cafe name (clickable → detail page), email, upload count, latest revenue, savings potential, signup date

**Cafe detail page** (`/admin/cafe/<id>`):
- Profile card — cafe name, email, signup date, total uploads
- Latest metrics — 5 cards: revenue, ticket, transactions, waste cost, savings
- Trends over time — week-by-week table showing revenue/waste/ticket changes with green/red indicators
- Upload history — every CSV they've uploaded with dates and metrics

### Other Admin URLs
- `/admin/backup` — triggers a manual database backup (emailed to you)
- `/health` — returns JSON with app status and all registered routes

---

## Database Backups

### Automatic (daily)
A background thread runs every 24 hours:
1. Copies the SQLite database safely (handles write-ahead log)
2. Saves to `/opt/render/project/data/backups/` with timestamp
3. Emails the backup to your Gmail as an attachment
4. Keeps last 7 backups, auto-deletes older ones

### Manual
Visit `/admin/backup` (requires admin auth). Returns JSON confirmation.

### Restoring from Backup
1. Download the `.db` file from your email
2. Open Render shell (Dashboard → your service → Shell tab)
3. Replace the database:
```bash
cp /opt/render/project/data/pulpiq.db /opt/render/project/data/pulpiq-pre-restore.db
cp pulpiq-backup-YYYY-MM-DD.db /opt/render/project/data/pulpiq.db
```
4. Trigger manual deploy from Render dashboard

### What's in the Database
- **users** — email, cafe name, created date
- **auth_tokens** — magic link tokens (expire after 15 min)
- **snapshots** — every upload's analysis results (flat metrics + full JSON blobs)

---

## New Customer Onboarding Flow

```
1. Owner visits trypulp.co
2. Landing page explains: what PulpIQ is, how it works (3 steps),
   what they'll see, pricing ($0), who it's for, FAQ
3. Clicks "Get My Free Report" → /login page
4. Enters email + cafe name → submits
5. NEW USERS ONLY: receives welcome email with:
   - Warmer subject: "Welcome to PulpIQ — Here's How to Get Started"
   - Onboarding PDF attached (POS export instructions for Square/Toast/Clover)
   - Personal copy from Paul
   - Magic link to sign in
6. RETURNING USERS: receives standard magic link email (no PDF)
7. Clicks magic link → new users go to /upload, returning users go to /dashboard
8. Uploads CSV → sees instant report
9. Returns weekly with new data → sees comparison page
```

---

## How Savings Are Calculated

### Perishable Waste Savings
```
For each perishable item:
  current_estimated_order = max quantity sold on any single day
  recommended_order = average daily sales + half a standard deviation
  daily_waste = current_estimated_order - average_daily_sales
  ingredient_cost = item's avg menu price × 30% COGS ratio
  monthly_waste = daily_waste × ingredient_cost × 30 days
  savings = current_monthly_waste - optimized_monthly_waste
```

### Milk Waste Savings
```
  daily_milk_cost = sum of (daily oz per type × cost per oz)
  assumed_waste = 10% of daily milk cost
  savings = 60% of that waste (realistic reduction target)
  monthly_milk_savings = daily savings × 30 days
```

### Total Savings
```
  total = perishable_savings + milk_savings
  capped at 15% of monthly revenue (prevents unrealistic claims)
```

### Cost Assumptions (Toronto CAD, 2025-2026)

| Item | Cost | Source |
|------|------|--------|
| Dairy milk | $0.04/oz (~$5.10/gal) | Saputo via foodservice distributor |
| Oat milk | $0.15/oz (~$4.50/946mL) | Oatly Barista case price |
| Almond milk | $0.14/oz (~$4.62/946mL) | Pacific Barista case price |
| Soy milk | $0.12/oz (~$3.83/946mL) | Pacific Barista case price |
| Coconut milk | $0.15/oz (~$4.75/946mL) | Pacific Barista case price |
| Perishable COGS | 30% of menu price | Industry avg, beverage-heavy cafe |

These live in `src/analysis/product_classifier.py` → `DEFAULT_COSTS`.

---

## Legal & Liability

### What We Have
1. **Report disclaimers** — every report and comparison page shows: "Savings estimates are based on your sales data and Toronto industry-average costs. Actual results depend on your specific suppliers, pricing, and implementation. These are projections, not guarantees."

2. **How We Calculate page** (`/methodology`) — full transparency on every number: revenue metrics, waste analysis formulas, milk estimation, cost assumptions with sources, product classification, week-over-week comparison methodology.

3. **Terms of Service** (`/terms`) — covers:
   - PulpIQ is informational, not financial advice
   - Savings are estimates, not guarantees
   - Data handling (we don't store raw CSVs, never share data)
   - Deletion on request within 7 business days
   - Limitation of liability
   - Governing law: Ontario, Canada

### Links
- Both pages linked in the footer of every page
- Both linked in the report disclaimer
- Methodology explains every formula in plain English

---

## Monetization Plan (Not Yet Built)

**Free tier:** First upload (baseline report) — always free. This is the marketing funnel.

**Paid tier ($29-49/month):** Weekly uploads with comparison tracking.

**Implementation:** Gate at `week_number > 0` — baseline is free, week 1+ checks for active Stripe subscription. Add a "Subscribe" CTA after the first report.

**The math:**
- 100 free users → 20% convert → 20 paying × $49/month = $980/month
- 50 paying cafes = $2,450/month

**When to build this:** After you have 5+ users who upload more than once (they're your future paying customers).

---

## Running Locally

```bash
# Install Python dependencies
pip install -r requirements.txt

# Build CSS (from src/webapp/)
cd src/webapp && npm install && npm run build:css && cd ../..

# Run dev server
python wsgi.py
```

App runs at **http://localhost:5000**. Magic links print to terminal (no emails in dev mode).

### Watch CSS during development
```bash
cd src/webapp && npm run watch:css
```

---

## Troubleshooting

### 502 Bad Gateway on Render
Check Render **Logs** tab. Most likely a missing env var or import error. Push a fix → auto-redeploys.

### Magic link emails not arriving
1. Check Render logs for `[AUTH]` lines
2. `SMTP_USER configured: no` → env var not set
3. `Email send FAILED: ...` → wrong Gmail app password
4. Magic link always prints in logs as fallback

### Upload errors
The validator shows specific error messages. Common issues: missing required columns, very short date range, non-CSV file. The app handles 40+ column name variations — if it still fails, the POS export is missing a required field.

### Analysis seems wrong
- Check CSV quality (weird items, $0 prices, short date range)
- Savings capped at 15% of monthly revenue
- Cost defaults are Toronto averages — ordering recommendations are still correct regardless

### Admin panel shows "Internal Server Error"
Usually a datetime formatting issue or None value. Check Render logs for the error JSON — it shows the exact error now.

### Database wiped after deploy
`DATABASE_PATH` env var isn't set, or no persistent disk attached in Render. Add both (see Environment Variables section above).

### Need to reset a user
```sql
sqlite3 /opt/render/project/data/pulpiq.db
DELETE FROM snapshots WHERE user_id = (SELECT id FROM users WHERE email = 'owner@cafe.com');
DELETE FROM auth_tokens WHERE user_id = (SELECT id FROM users WHERE email = 'owner@cafe.com');
DELETE FROM users WHERE email = 'owner@cafe.com';
```

---

## Project Structure

```
src/
  analysis/                     # Analysis engine (pure Python, no Flask dependency)
    customer_intelligence.py    # Revenue, top items, categories, trends, all items
    waste_analysis.py           # Perishable waste, milk usage, order recommendations
    validate_data.py            # CSV validation + column mapping (40+ aliases)
    product_classifier.py       # Auto-classify items, cost defaults (Toronto CAD)

  webapp/                       # Flask web app
    __init__.py                 # App factory, admin routes, backup scheduler
    models.py                   # SQLite: users, tokens, snapshots, admin queries
    auth.py                     # Magic link generation + email + onboarding PDF
    onboarding_pdf.py           # Generates POS export instructions PDF
    backup.py                   # Database backup + email delivery
    analysis_runner.py          # Calls analysis modules, serializes pandas → JSON
    views/
      auth_views.py             # /login, /verify, /logout
      upload_views.py           # /upload, comparison builder, item movers, actions
      dashboard_views.py        # /dashboard, /report/<id>, /compare/<id>
    templates/
      base.html                 # Shared layout (nav, footer, flash messages)
      login.html                # Landing + signup form
      check_email.html          # "Check your inbox" with spam tips
      upload.html               # Drag-and-drop CSV upload
      dashboard.html            # Metrics + upload history
      report.html               # Full analysis with category filtering
      comparison.html           # Week-over-week with baseline, savings, movers, actions
      methodology.html          # How we calculate (public)
      terms.html                # Terms of Service (public)
      admin_users.html          # Admin: all users + savings ranking
      admin_cafe.html           # Admin: individual cafe detail + trends
    static/
      input.css                 # Tailwind source (theme, animations, tooltips, pills)
      styles.css                # Compiled CSS (committed to repo)

  website/                      # Landing page (served by Flask at /)
    index.html                  # Marketing page with images
    *.jpg, *.png                # Landing page images (served via /site/ route)

wsgi.py                         # Entry point
requirements.txt                # Python dependencies: flask, pandas, numpy, reportlab, etc.
render.yaml                     # Render deployment config
```

---

## All Routes

| Route | Auth | What It Does |
|-------|------|-------------|
| `/` | No | Landing page (logged out) or redirect to dashboard (logged in) |
| `/login` | No | Signup/login form |
| `/verify?token=` | No | Magic link verification |
| `/logout` | Session | Clears session |
| `/upload` | Session | CSV upload form + processing |
| `/dashboard` | Session | Metrics + upload history |
| `/report/<id>` | Session | Full analysis report |
| `/compare/<id>` | Session | Week-over-week comparison |
| `/methodology` | No | How we calculate (public) |
| `/terms` | No | Terms of Service (public) |
| `/health` | No | App status + route list (JSON) |
| `/site/<filename>` | No | Landing page images |
| `/admin/users` | Basic Auth | All users + savings ranking |
| `/admin/cafe/<id>` | Basic Auth | Individual cafe detail |
| `/admin/backup` | Basic Auth | Trigger database backup |
