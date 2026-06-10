"""
send_email.py
-------------
Runs Mon–Fri via GitHub Actions (triggered at both 15:00 and 16:00 UTC).
Checks whether it is currently 11 AM ET (accounting for EST/EDT).
If yes: fetches the live PSUS price from Yahoo Finance, calculates the
discount to the most recent published NAV, and sends the daily email.
If no:  exits silently — the other UTC trigger will handle it.
"""

import csv
import os
import smtplib
import sys
from datetime import date, datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import yfinance as yf

RECIPIENT      = "jhaik852@gmail.com"
CSV_PATH       = os.path.join(os.path.dirname(__file__), "..", "data", "psus_nav_database.csv")
TICKER         = "PSUS"
TARGET_HOUR_ET = 11   # 11 AM ET


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

def is_dst(dt_utc: datetime) -> bool:
    """
    Return True if New York is observing EDT (UTC-4) at the given UTC time.
    US DST: second Sunday in March → first Sunday in November.
    """
    year = dt_utc.year

    # Second Sunday in March
    march_1  = datetime(year, 3, 1, tzinfo=timezone.utc)
    dst_start = march_1 + timedelta(days=(6 - march_1.weekday()) % 7 + 7)
    dst_start = dst_start.replace(hour=7)  # 07:00 UTC = 02:00 EST → clocks spring forward

    # First Sunday in November
    nov_1    = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end  = nov_1 + timedelta(days=(6 - nov_1.weekday()) % 7)
    dst_end  = dst_end.replace(hour=6)    # 06:00 UTC = 02:00 EDT → clocks fall back

    return dst_start <= dt_utc < dst_end


def et_hour(dt_utc: datetime) -> int:
    offset = -4 if is_dst(dt_utc) else -5
    return (dt_utc.hour + offset) % 24


def check_et_time() -> bool:
    """Return True only if it is currently 11 AM ET (within the current UTC hour)."""
    now_utc = datetime.now(timezone.utc)
    current_et_hour = et_hour(now_utc)
    if current_et_hour != TARGET_HOUR_ET:
        print(
            f"[send_email] Current ET hour is {current_et_hour}:xx — "
            f"not {TARGET_HOUR_ET} AM ET. Exiting silently."
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def get_latest_nav() -> dict:
    """Return the most recent row that has a NAV value."""
    rows = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["nav_per_share"].strip():
                rows.append(row)
    if not rows:
        raise ValueError("No NAV data found in database.")
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows[0]


def get_live_price() -> tuple[float, str]:
    """
    Fetch the last sale price during regular market hours from Yahoo Finance.
    Uses 1-minute intraday bars with prepost=False (default) so pre/post-market
    trades are excluded. Falls back to the most recent daily close.
    Returns (price, source_description).
    """
    ticker = yf.Ticker(TICKER)

    # 1-min bars for today's regular session only
    hist = ticker.history(period="1d", interval="1m")
    if not hist.empty:
        price = round(float(hist["Close"].iloc[-1]), 2)
        return price, "Yahoo Finance (regular market hours)"

    # Fallback: most recent daily close
    hist = ticker.history(period="5d")
    if hist.empty:
        raise ValueError("Yahoo Finance returned no price data for PSUS.")
    price = round(float(hist["Close"].iloc[-1]), 2)
    price_date = hist.index[-1].strftime("%Y-%m-%d")
    return price, f"Yahoo Finance (close {price_date})"


def append_daily_price(price: float, discount: float) -> None:
    """Append today's price to the CSV if not already present."""
    today_str = str(date.today())
    rows = []
    fieldnames = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if any(r["date"] == today_str for r in rows):
        return  # Already logged today

    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow({
            "date":          today_str,
            "period":        "Daily",
            "nav_per_share": "",
            "nyse_price":    price,
            "discount_pct":  discount,
        })


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def build_email(
    price: float,
    price_source: str,
    nav: float,
    nav_date: str,
    nav_period: str,
    discount: float,
) -> tuple[str, str]:
    """Return (subject, html_body)."""

    sign      = "+" if discount >= 0 else ""
    disc_str  = f"{sign}{discount:.2f}%"
    today_str = datetime.now().strftime("%A, %B %d, %Y")

    # Colour: red > 15% discount, orange 5–15%, green < 5%
    if discount <= -15:
        disc_colour = "#C0392B"
    elif discount <= -5:
        disc_colour = "#E67E22"
    else:
        disc_colour = "#27AE60"

    subject = (
        f"PSUS ${price:.2f} | {disc_str} discount to NAV "
        f"(${nav:.2f} as of {nav_date})"
    )

    body = f"""
<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;
             max-width: 520px; margin: 0 auto; padding: 20px;">

  <h2 style="margin: 0 0 4px; color: #1a1a2e; font-size: 18px;">
    PSUS Daily Update
  </h2>
  <p style="margin: 0 0 20px; color: #888; font-size: 13px;">{today_str}</p>

  <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
    <tr style="background: #f7f7f7;">
      <td style="padding: 12px 14px; border: 1px solid #e0e0e0; font-weight: bold; width: 45%;">
        Share price
      </td>
      <td style="padding: 12px 14px; border: 1px solid #e0e0e0;">
        <strong>${price:.2f}</strong>
        <span style="font-size: 12px; color: #999; margin-left: 6px;">
          {price_source}
        </span>
      </td>
    </tr>
    <tr>
      <td style="padding: 12px 14px; border: 1px solid #e0e0e0; font-weight: bold;">
        Latest NAV
      </td>
      <td style="padding: 12px 14px; border: 1px solid #e0e0e0;">
        <strong>${nav:.2f}</strong>
        <span style="font-size: 12px; color: #999; margin-left: 6px;">
          {nav_period}, as of {nav_date}
        </span>
      </td>
    </tr>
    <tr style="background: #f7f7f7;">
      <td style="padding: 12px 14px; border: 1px solid #e0e0e0; font-weight: bold;">
        Discount to NAV
      </td>
      <td style="padding: 12px 14px; border: 1px solid #e0e0e0;">
        <strong style="font-size: 16px; color: {disc_colour};">{disc_str}</strong>
      </td>
    </tr>
  </table>

  <p style="margin-top: 24px; font-size: 11px; color: #aaa; line-height: 1.6;">
    Price source: {price_source}<br>
    NAV source: pershingsquareusa.com/performance (published each Wednesday)<br>
    NAV is calculated as of Tuesday close. Month-end NAV replaces weekly where applicable.<br>
    Discount = (share price ÷ NAV) − 1
  </p>

</body>
</html>
"""
    return subject, body


def send_email(subject: str, body: str) -> None:
    sender   = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, RECIPIENT, msg.as_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[send_email] Running on {date.today()} UTC {datetime.now(timezone.utc).strftime('%H:%M')}")

    # if not check_et_time():
    #    sys.exit(0)

    nav_row    = get_latest_nav()
    nav        = float(nav_row["nav_per_share"])
    nav_date   = nav_row["date"]
    nav_period = nav_row["period"]

    price, price_source = get_live_price()

    discount = round((price / nav - 1) * 100, 2)

    subject, body = build_email(price, price_source, nav, nav_date, nav_period, discount)

    send_email(subject, body)
    print(f"[send_email] Sent: {subject}")

    append_daily_price(price, discount)
    print(f"[send_email] Logged price ${price:.2f} to database.")


if __name__ == "__main__":
    main()
