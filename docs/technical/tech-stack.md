# Tech Stack - PulpIQ Platform

**Last Updated:** March 27, 2026  
**Phase:** MVP / Validation

---

## Stack Overview

PulpIQ uses a **lean, low-cost stack** optimized for manual analysis during validation phase. No complex infrastructure until demand is proven.

**Philosophy:** Manual first, automate later. Prove value before building software.

---

## Phase 1: MVP / Pilot (Current)

### Website & Landing Page

**Option A: Carrd** (Recommended for speed)
- **Cost:** $19/year
- **Pros:** Dead simple, beautiful templates, perfect for landing pages
- **Cons:** Limited customization
- **Use case:** Single-page marketing site with form

**Option B: Webflow**
- **Cost:** Free tier (includes basic hosting)
- **Pros:** More design control, CMS included
- **Cons:** Steeper learning curve
- **Use case:** If you want blog/content pages

**Option C: Custom HTML/CSS**
- **Cost:** Free (host on GitHub Pages or Netlify)
- **Pros:** Full control, can customize everything
- **Cons:** Requires frontend coding
- **Use case:** If you're comfortable coding

**Recommendation:** **Carrd** for speed. Ship in 1 day, iterate later.

---

### Domain & DNS

**Domain Registrar:**
- **Namecheap** or **Cloudflare Registrar**
- **Cost:** $30-40/year for pulpiq.io
- **Why:** At-cost pricing, no markup

**DNS/CDN:**
- **Cloudflare** (free tier)
- **Benefits:** Fast DNS, SSL certificate, DDoS protection
- **Setup:** Point domain to Carrd/Webflow

---

### Email & Forms

**Email Automation:**
**Option A: Mailchimp** (Recommended)
- **Cost:** Free up to 500 contacts
- **Features:** Automation sequences, templates, analytics
- **Use case:** Welcome emails, weekly report delivery

**Option B: ConvertKit**
- **Cost:** Free up to 300 subscribers
- **Features:** Better automation than Mailchimp
- **Use case:** If you want more sophisticated email funnels

**Form Collection:**
- **Google Forms** → **Google Sheets** (Free)
- **Typeform** (Free tier: 10 responses/month)
- **Tally** (Free, unlimited)

**Recommendation:** Mailchimp + Google Forms

---

### Data Collection & Storage

**File Uploads:**
- **Google Drive** (Free 15GB)
- **Dropbox File Requests** (Free with basic account)

**Data Organization:**
- **Google Sheets** (for tracking pilot cafés, metrics)
- **Airtable** (Free tier, more powerful than Sheets)

**File naming convention:**
```
/cafes/[cafe-name]/
  - sales-data-raw.csv
  - inventory-purchases.csv
  - staff-schedules.csv
  - baseline-report.pdf
  - week-1-insights.pdf
```

---

### Payment Processing

**Stripe**
- **Cost:** Free (2.9% + 30¢ per transaction)
- **Features:** Subscription billing, payment links
- **Setup:** Create $199/month recurring subscription product

**Payment Links:**
```
https://buy.stripe.com/your-product-link
```
Embed in email: "Continue with PulpIQ - $199/month"

---

### Analytics & Tracking

**Website Analytics:**
**Option A: Plausible**
- **Cost:** $9/month
- **Pros:** Privacy-friendly, simple, no cookie banners
- **Cons:** Not free

**Option B: Google Analytics 4**
- **Cost:** Free
- **Pros:** Powerful, industry standard
- **Cons:** Complex, privacy concerns

**Recommendation:** Start with Google Analytics (free), switch to Plausible if budget allows.

**Key metrics to track:**
- Landing page visits
- Form submissions
- Conversion rate (visitor → signup)
- Email open rates
- Data upload completion rate

---

### Communication

**Scheduling:**
- **Calendly** (Free tier)
- **Use case:** Book kickoff calls with pilots

**Video Calls:**
- **Zoom** (Free tier: 40 min limit)
- **Google Meet** (Free with Gmail)

**Support:**
- **Gmail** (paul@pulpiq.io via Google Workspace)
- **Cost:** $6/month per user
- **Features:** Custom domain email, 30GB storage

---

## Data Analysis Stack (Python)

### Environment Setup

**Python Version:** 3.10+

**Package Manager:**
```bash
pip install --upgrade pip
```

**Virtual Environment:**
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate  # Windows
```

---

### Core Libraries

**Data Manipulation:**
```bash
pip install pandas numpy
```
- **pandas:** CSV reading, data manipulation
- **numpy:** Numerical operations

**Visualization:**
```bash
pip install matplotlib seaborn plotly
```
- **matplotlib:** Basic charts
- **seaborn:** Statistical visualizations
- **plotly:** Interactive charts for reports

**Machine Learning (Optional for MVP):**
```bash
pip install scikit-learn
```
- **Use case:** Predictive models for waste, demand forecasting

**Date/Time:**
```bash
pip install python-dateutil
```
- **Use case:** Handling timestamps, date parsing

**PDF Generation:**
```bash
pip install reportlab
```
- **Use case:** Generate PDF reports

---

### Analysis Scripts Structure

```
src/analysis/
├── waste_analysis.py       # Inventory & waste predictions
├── labor_optimization.py   # Staffing recommendations
├── customer_intelligence.py # VIP tracking, churn prediction
├── report_generator.py     # Create weekly PDF/HTML reports
└── utils.py               # Shared functions (data cleaning, etc.)
```

**Example usage:**
```bash
python src/analysis/waste_analysis.py --input data/cafe-name/sales-data.csv --output reports/cafe-name/week-1-waste.pdf
```

---

### Data Processing Pipeline

**Step 1: Data Ingestion**
```python
import pandas as pd

# Read CSV from café
sales = pd.read_csv('data/cafe/sales-data.csv')
inventory = pd.read_csv('data/cafe/inventory-purchases.csv')
```

**Step 2: Data Cleaning**
```python
# Standardize column names
sales.columns = sales.columns.str.lower().str.replace(' ', '_')

# Parse dates
sales['date'] = pd.to_datetime(sales['date'])

# Remove duplicates
sales = sales.drop_duplicates()
```

**Step 3: Analysis**
```python
# Example: Calculate waste
daily_sales = sales.groupby('item')['quantity'].sum()
daily_ordered = inventory.groupby('item')['quantity'].sum()
waste = daily_ordered - daily_sales
```

**Step 4: Generate Insights**
```python
# Example: Identify overordered items
overordered = waste[waste > 0].sort_values(ascending=False)
recommendations = f"Reduce {overordered.index[0]} order by {overordered.iloc[0]} units/week"
```

**Step 5: Create Report**
```python
# Generate PDF or HTML email
from report_generator import create_weekly_report
create_weekly_report(cafe_name='Blue Bottle', insights=recommendations)
```

---

## Phase 2: Automated Platform (Future)

*Only build if pilot succeeds*

### Backend

**Framework:** 
- **Flask** (Python) or **FastAPI**
- **Why:** Simple, fast to build

**Database:**
- **PostgreSQL** (Heroku free tier or Railway)
- **Why:** Structured data (cafés, sales, insights)

**File Storage:**
- **AWS S3** (pay-as-you-go)
- **Why:** Scalable CSV storage

**Job Queue:**
- **Celery** + **Redis**
- **Why:** Background tasks (run analysis weekly)

---

### Frontend

**Dashboard Framework:**
- **React** or **Vue.js**
- **Component library:** shadcn/ui or Tailwind UI

**Features:**
- Upload CSV
- View weekly reports
- Track savings over time
- Download insights as PDF

---

### Hosting & Infrastructure

**Option A: Heroku** (Easiest)
- **Cost:** $7/month (Eco Dyno)
- **Pros:** Zero DevOps, just git push
- **Cons:** More expensive at scale

**Option B: Railway** (Modern alternative)
- **Cost:** ~$5/month starter
- **Pros:** Better UX than Heroku, same simplicity

**Option C: DigitalOcean / AWS** (Most control)
- **Cost:** $12/month (basic droplet)
- **Pros:** Full control, cheaper at scale
- **Cons:** Requires more DevOps knowledge

**Recommendation:** Heroku for MVP, migrate to Railway/DO if needed

---

### API Integrations (Future)

**POS Integrations (Phase 3):**
- **Square API:** Real-time sales data
- **Toast API:** Menu items, transactions
- **Clover API:** Inventory, sales

**Benefits:** 
- No manual CSV uploads
- Real-time insights
- Automated weekly reports

**Complexity:** 
- Requires OAuth, webhooks
- Each POS has different API
- Build only after validation

---

## Development Tools

### Version Control
- **GitHub** (free for private repos)
- **Repo:** github.com/paulspry/pulpiq

### Code Editor
- **VS Code** (free)
- **Extensions:** 
  - Python
  - Pylance
  - GitLens
  - Prettier

### Testing (Future)
- **pytest** (Python unit tests)
- **Postman** (API testing)

---

## Security & Compliance

### Data Security (MVP)
- **Encryption at rest:** Google Drive has built-in encryption
- **Encryption in transit:** HTTPS via Cloudflare
- **Access control:** Password-protected Google Drive folders

### GDPR / Privacy (Future)
- **Data deletion:** Provide "delete my data" button
- **Privacy policy:** Use Termly or TermsFeed generator (free)
- **Cookie consent:** Use Cookiebot (free tier)

---

## Cost Breakdown (Monthly)

### Phase 1 (MVP / Pilot):
| Item | Cost |
|------|------|
| Domain (pulpiq.io) | $3/month (amortized) |
| Website (Carrd) | $2/month (amortized) |
| Email (Google Workspace) | $6/month |
| Analytics (Google Analytics) | Free |
| Forms (Google Forms) | Free |
| Email automation (Mailchimp) | Free (under 500 contacts) |
| File storage (Google Drive) | Free |
| Payment processing (Stripe) | 2.9% of revenue |
| **Total fixed cost** | **~$11/month** |

### Phase 2 (Automated Platform):
| Item | Cost |
|------|------|
| Phase 1 costs | $11/month |
| Hosting (Heroku) | $7/month |
| Database (PostgreSQL) | Free (Heroku tier) |
| Redis (for Celery) | Free (Railway tier) |
| Analytics (Plausible) | $9/month |
| **Total fixed cost** | **~$27/month** |

### Phase 3 (Scale):
- Hosting: $50-200/month (as you grow)
- Support tools (Intercom): $50/month
- **Total:** $100-300/month

---

## Development Roadmap

### Week 1: MVP Setup
- [ ] Buy domain (pulpiq.io)
- [ ] Build landing page (Carrd)
- [ ] Set up Google Workspace email
- [ ] Create Mailchimp account
- [ ] Configure Google Forms
- [ ] Set up Stripe payment link

### Week 2-3: Analysis Scripts
- [ ] Write Python scripts for:
  - Waste analysis
  - Labor optimization
  - Customer intelligence
- [ ] Create report templates (PDF/HTML)
- [ ] Test with sample café data

### Week 4: Pilot Launch
- [ ] Onboard first pilots
- [ ] Collect data
- [ ] Generate first reports

### Week 5-10: Iteration
- [ ] Improve analysis scripts based on feedback
- [ ] Automate report generation
- [ ] Track metrics in Google Sheets

### Week 11+: Decide
- [ ] If successful → Build Phase 2 (automated platform)
- [ ] If unsuccessful → Pivot or kill

---

## Recommended Tools Summary

**Must-have (Week 1):**
- ✅ Carrd (website)
- ✅ Namecheap (domain)
- ✅ Google Workspace (email)
- ✅ Mailchimp (automation)
- ✅ Google Forms + Drive (data collection)
- ✅ Stripe (payments)

**Nice-to-have (Week 2+):**
- Calendly (scheduling)
- Airtable (better than Sheets)
- Plausible (privacy-friendly analytics)

**Don't need yet:**
- Custom backend
- Database
- API integrations
- Dashboard

---

## Next Steps

1. **Install Python dependencies:**
```bash
pip install pandas numpy matplotlib seaborn reportlab
```

2. **Set up accounts:**
- Carrd: carrd.co
- Namecheap: namecheap.com
- Google Workspace: workspace.google.com
- Mailchimp: mailchimp.com
- Stripe: stripe.com

3. **Start building:**
- Landing page first
- Analysis scripts second
- Everything else as needed

---

**Total startup cost: <$50**  
**Time to launch: 1 week**

Let's ship it.
