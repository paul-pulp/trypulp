# PulpIQ — Product Owner Guide

## The Business

PulpIQ is a self-serve analytics tool for independent cafe owners. They upload their POS sales data (a CSV file) and instantly see what's selling, what's going unsold, and exactly what to change. They come back weekly to track their progress.

**The value proposition:** Most indie cafes waste $500–1,500/month on over-ordering and don't have time to dig through spreadsheets. PulpIQ does the analysis in seconds.

**The business model:**
- **Free:** First upload (Week 1 report) + 2 free weekly uploads
- **Pro ($49/month):** Unlimited weekly uploads, week-over-week tracking, cumulative savings, item movers, weekly action items
- **Billing:** Stripe Checkout with subscription management via Customer Portal

**Target market:** Independent cafes in Toronto, Canada. Any size, any POS system (Square, Toast, Clover, or anything that exports CSV).

---

## What We Do for the Cafe Owner

### First Visit (Free)
1. Owner lands on **trypulp.co** — landing page with "Get Free Report" CTA + sticky bottom bar on scroll
2. Clicks CTA → enters email + cafe name on `/login`
3. Receives magic link email from "PulpIQ" (no password) with **onboarding PDF** attached (POS export instructions for Square, Toast, Clover)
4. Clicks magic link → lands directly on the **upload page** (not empty dashboard)
5. Drags in their CSV → sees instant results in 2-5 seconds

### What They See in Their Report
- **Key Findings** — 3 plain-English bullets ("Your biggest seller is X. You're wasting $Y/month on items that go unsold. Reducing Z could save $W/month.")
- **All Items** — every product with category filtering (Beverage / Food / Pastry pills with counts)
- **Your Menu Breakdown** — sales by category with progress bars
- **Revenue by Day of Week** — best/worst days with inline bars
- **Revenue by Hour** — when the money comes in
- **How Your Customers Pay** — credit vs cash, average sale per method
- **Hot vs Iced** — drink temperature split
- **Where You Could Save** — unsold items per day, estimated monthly waste, savings potential
- **Waste Table** — per-item: you sell/day, you likely order, recommended, wasted $/month
- **Your Milk Breakdown** — dairy/oat/almond usage and ordering recommendations
- **Insight callouts** — "Biggest opportunity: reduce X orders from Y to Z/day"
- **Print button** for sharing with partners
- **Delete button** on most recent upload (to re-upload if wrong file)

### Weekly Return (Pro — $49/month)
1. Owner logs in → uploads new week's CSV
2. Sees **week-over-week comparison** with:
   - Every metric shows **vs last week** AND **vs your first week** (total progress)
   - **Cumulative savings tracker** — "You've saved an estimated $X since joining PulpIQ"
   - **Items that changed most** — top 4 products with up/down arrows and % change
   - **Your Focus This Week** — 2-3 specific action items based on the data
3. Dashboard shows upload history with all past reports

### Trial Flow
- Week 1 upload: always free
- 2 more free weekly uploads to try the tracking features
- After that: paywall → `/upgrade` page → Stripe Checkout → $49/month
- Upload page shows trial remaining: "You have X free uploads left"
- Dashboard shows "Upgrade to Pro" CTA when trial exhausted

### What Auto-Adapts (No Configuration Needed)
- Column names — 60+ POS variations mapped automatically
- Combined datetime columns — auto-split into date + time
- Missing quantity column — auto-fills as 1 per line item
- Missing time column — auto-fills as 12:00
- Bad dates/times — skips bad rows, analyzes the rest
- Duplicate column names (Unit Price + Total) — handled gracefully
- Short data ranges — warns but still runs (no blocking)
- Only blocks if there's no price/total column at all

---

## The Tech Stack

| Tool | What It Does | Cost |
|------|-------------|------|
| **Flask** (Python) | Web app — pages, analysis, auth | Free |
| **SQLite** | Database — users, uploads, results | Free |
| **Tailwind CSS** | Styling — compiled via CLI | Free |
| **Render.com** | Hosts the app + persistent disk | Free tier / $7/mo |
| **Stripe** | Subscription payments ($49/month) | 2.9% + $0.30 per transaction |
| **GitHub** | Code repository — push to deploy | Free |
| **Gmail SMTP** | Magic link emails, onboarding PDFs, feedback notifications | Free |
| **GoDaddy** | Domain: trypulp.co | ~$15/year |
| **pandas/numpy** | Analysis engine | Free |
| **reportlab** | Generates onboarding PDF | Free |
| **Fraunces** | Display font (Google Fonts) | Free |

---

## Where Everything Lives

| What | Where | URL |
|------|-------|-----|
| Live site | Render.com | **trypulp.co** |
| Code | GitHub | github.com/paul-pulp/trypulp |
| Database | SQLite on Render persistent disk | /opt/render/project/data/pulpiq.db |
| Payments | Stripe | dashboard.stripe.com |
| Domain DNS | GoDaddy | A record → 216.24.57.1 |

---

## How Deploys Work

Push to `main` on GitHub → Render auto-deploys in ~2 minutes.

```bash
git add -A && git commit -m "description" && git push origin main
```

---

## Environment Variables (Render → Environment Tab)

| Variable | What It Does |
|----------|-------------|
| `SECRET_KEY` | Signs session cookies (auto-generated) |
| `DATABASE_PATH` | `/opt/render/project/data/pulpiq.db` |
| `APP_URL` | `https://trypulp.co` |
| `SMTP_USER` | Gmail address for sending emails |
| `SMTP_PASS` | Gmail app password |
| `ADMIN_USER` | Username for admin panel |
| `ADMIN_PASS` | Password for admin panel |
| `STRIPE_SECRET_KEY` | `sk_live_...` from Stripe |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` from Stripe |
| `STRIPE_PRICE_ID` | `price_...` for the $49/month plan |

**Render also needs a persistent disk:**
- Mount path: `/opt/render/project/data`
- Size: 1 GB

---

## Admin Panel

**Users:** `trypulp.co/admin/users` — all signups sorted by savings potential, clickable to detail page

**Cafe detail:** `trypulp.co/admin/cafe/<id>` — metrics, trends over time, upload history

**Feedback:** `trypulp.co/admin/feedback` — all customer feedback with type badges

**Backup:** `trypulp.co/admin/backup` — triggers manual database backup (emailed to you)

**Health:** `trypulp.co/health` — app status and registered routes

All admin routes protected by HTTP Basic Auth (`ADMIN_USER` / `ADMIN_PASS`).

---

## Database Backups

**Automatic:** Background thread runs every 24 hours — copies SQLite, emails it to your Gmail, keeps last 7 on disk.

**Manual:** Visit `/admin/backup`

**Restore:** Download `.db` from email → Render Shell → replace file → redeploy.

---

## Emails the System Sends

| When | To | Subject | Includes |
|------|-----|---------|----------|
| New signup | Customer | "Welcome to PulpIQ — Here's How to Get Started" | Magic link + onboarding PDF |
| Returning login | Customer | "Your PulpIQ Sign-In Link" | Magic link only |
| Subscribes to Pro | Customer | "Welcome to PulpIQ Pro, [Cafe]!" | What they can do + dashboard link |
| Feedback submitted | hello@trypulp.co | "[PulpIQ Feature Request] Cafe Name" | Full feedback message |
| Daily backup | Your Gmail | "PulpIQ Database Backup" | .db file attachment |

All emails sent from "PulpIQ" (not personal name).

---

## How Savings Are Calculated

### Items that go unsold
```
For each item that spoils:
  you_likely_order = max quantity sold on any single day
  recommended = average daily sales + small safety cushion
  unsold_per_day = you_likely_order - average_daily_sales
  ingredient_cost = menu price × 30% (average ingredient cost)
  monthly_waste = unsold × ingredient_cost × 30 days
```

### Milk waste
```
  daily_milk_cost = sum of (daily oz per type × cost per oz)
  assumed_waste = 10% of daily milk cost
  savings = 60% of that waste
```

### Total
```
  total = item savings + milk savings
  capped at 15% of monthly sales (prevents unrealistic claims)
```

### Cost Assumptions (Toronto CAD, 2025-2026)

| Item | Cost | Source |
|------|------|--------|
| Dairy milk | $0.04/oz (~$5.10/gal) | Saputo wholesale |
| Oat milk | $0.15/oz (~$4.50/946mL) | Oatly Barista case |
| Almond milk | $0.14/oz (~$4.62/946mL) | Pacific Barista case |
| Soy milk | $0.12/oz (~$3.83/946mL) | Pacific Barista case |
| Coconut milk | $0.15/oz (~$4.75/946mL) | Pacific Barista case |
| Ingredient cost | 30% of menu price | Industry avg |

---

## Legal & Liability

- **Report disclaimers** on every report and comparison page
- **How We Calculate** page at `/methodology` — full transparency
- **Terms of Service** at `/terms` — not financial advice, estimates not guarantees, data deletion on request
- Footer links on every page

---

## Monetization

| Tier | What | Price |
|------|------|-------|
| **Free** | Week 1 report + 2 free weekly uploads | $0 |
| **Pro** | Unlimited weekly uploads + full tracking | $49/month |

Paywall triggers when trial uploads are exhausted. Stripe Checkout handles payment. Customer Portal handles cancellations.

---

## All Routes

| Route | Auth | What It Does |
|-------|------|-------------|
| `/` | No | Landing page (visitors) or → dashboard (logged in) |
| `/login` | No | Signup/login form |
| `/verify?token=` | No | Magic link verification |
| `/logout` | Session | Clears session |
| `/upload` | Session | CSV upload + processing |
| `/dashboard` | Session | Metrics + history + feedback form |
| `/report/<id>` | Session | Full analysis report |
| `/report/<id>/delete` | Session | Delete most recent upload |
| `/compare/<id>` | Session | Week-over-week comparison |
| `/subscribe` | Session | → Stripe Checkout |
| `/upgrade` | Session | Paywall / upgrade page |
| `/billing/success` | Session | Post-checkout activation |
| `/billing/cancel` | Session | Checkout cancelled |
| `/billing/manage` | Session | → Stripe Customer Portal |
| `/feedback` | Session | Submit feedback (POST) |
| `/methodology` | No | How we calculate (public) |
| `/terms` | No | Terms of Service (public) |
| `/health` | No | App status (JSON) |
| `/site/<filename>` | No | Landing page images |
| `/admin/users` | Basic Auth | All users + savings ranking |
| `/admin/cafe/<id>` | Basic Auth | Individual cafe detail |
| `/admin/feedback` | Basic Auth | Customer feedback |
| `/admin/backup` | Basic Auth | Trigger database backup |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 502 on Render | Check Logs tab. Usually missing env var or import error. Push fix → auto-redeploys. |
| Magic link not arriving | Check Render logs for `[AUTH]`. Link also prints in logs as fallback. |
| Upload error | Validator shows specific message. Only blocks if no price column found. |
| Stripe "something went wrong" | Check `[BILLING]` in logs. Usually wrong API key mode (test vs live). |
| Stale Stripe customers | Run in Render Shell: `sqlite3 /data/pulpiq.db "UPDATE users SET stripe_customer_id = NULL;"` |
| Database wiped | `DATABASE_PATH` not set or no persistent disk. Add both. |
| Admin 404 | Redeploy after changing `ADMIN_USER`/`ADMIN_PASS`. |

---

## Running Locally

```bash
pip install -r requirements.txt
cd src/webapp && npm install && npm run build:css && cd ../..
python wsgi.py
```

App at **http://localhost:5000**. Magic links print to terminal.
