# PSUS NAV & Discount Tracker

Automated tracker for Pershing Square USA, Ltd. (NYSE: PSUS).

- **Every Wednesday at 1 PM ET** — scrapes the latest NAV from pershingsquareusa.com and commits it to the database.
- **Every weekday at 11 AM ET** — fetches the live PSUS share price from Yahoo Finance, calculates the discount to the most recent published NAV, and sends a summary email.

---

## Repository structure

```
psus-tracker/
├── .github/workflows/
│   ├── nav_scraper.yml       # Wednesday NAV scrape
│   └── daily_email.yml       # Mon–Fri 11 AM ET email
├── scripts/
│   ├── scrape_nav.py         # NAV scraper
│   └── send_email.py         # Price fetch + email sender
└── data/
    └── psus_nav_database.csv # Persistent database
```

---

## One-time setup (15 minutes total)

### Step 1 — Create a Gmail App Password

You must use an App Password, not your regular Gmail password.

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Click **Security** → **2-Step Verification** (enable if not already on)
3. Search for **App passwords** at the top of the Security page
4. Click **Create app password**, name it `PSUS Tracker`
5. Copy the 16-character code — you will need it in Step 3

### Step 2 — Create the GitHub repository

1. Go to [github.com](https://github.com) and sign in with jhaik852@gmail.com
2. Click **New repository** (top right, green button)
3. Name it `psus-tracker`
4. Set it to **Private**
5. Click **Create repository**
6. Upload all files from this folder maintaining the same folder structure

### Step 3 — Add GitHub Secrets

Secrets are encrypted — GitHub never exposes them in logs.

1. In your repository, go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add the following two secrets:

| Secret name | Value |
|---|---|
| `GMAIL_ADDRESS` | jhaik852@gmail.com |
| `GMAIL_APP_PASSWORD` | The 16-character code from Step 1 |

### Step 4 — Enable GitHub Actions

1. Click the **Actions** tab in your repository
2. If prompted, click **I understand my workflows, go ahead and enable them**

### Step 5 — Test manually

1. Go to **Actions** → **Send PSUS Daily Email** → **Run workflow**
2. Check jhaik852@gmail.com for the email (arrives within ~60 seconds)
3. If no email: check the workflow run log for error messages

---

## Email format

**Subject:**
```
PSUS $38.17 | -21.99% discount to NAV ($48.93 as of 2026-05-31)
```

**Body:** HTML table with share price, latest NAV, discount, and data sources.

---

## Database format

`data/psus_nav_database.csv`

| Column | Description |
|---|---|
| `date` | YYYY-MM-DD |
| `period` | IPO / Weekly / Monthly / Daily |
| `nav_per_share` | Published NAV (blank for Daily price-only rows) |
| `nyse_price` | NYSE closing or live price |
| `discount_pct` | (price / NAV − 1) × 100 |

---

## How discount is calculated

```
Discount (%) = (share price ÷ most recent published NAV − 1) × 100
```

The most recent NAV is always used regardless of how many days have passed since publication.

---

## Monitoring

- Every workflow run is logged under the **Actions** tab
- Failed runs trigger an automatic email from GitHub to jhaik852@gmail.com
- If the PSUS website changes its layout, `scrape_nav.py` will exit with an error — visible in the Actions log

---

## NAV publication rules (per PSUS prospectus)

- NAV calculated as of **Tuesday close**, published **Wednesday**
- In weeks containing a month-end, the **month-end NAV replaces** the Tuesday NAV
- If Tuesday is a holiday, NAV is calculated as of the preceding business day
