"""
send_email.py
-------------
Runs Mon-Fr via GitHub Actions (triggered at both 15:00 and 16:00 UTC).
Checks whether it is currently 11 AM ET (accounting for EST/EDT).
If yes: fetches the live PSUS price from Yahoo Finance, calculates the
discount to the most recent published NAV, and sends the daily email.
If no:  exits silently - the other UTC trigger will handle it.
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
TARGET_HOUR_ET = 11


def is_dst(dt_utc: datetime) -> bool:
    year = dt_utc.year
    march_1   = datetime(year, 3, 1, tzinfo=timezone.utc)
    dst_start = march_1 + timedelta(days=(6 - march_1.weekday()) % 7 + 7)
    dst_start = dst_start.replace(hour=7)
    nov_1     = datetime(year, 11, 1, tzinfo=timezone.utc)
    dst_end   = nov_1 + timedelta(days=(6 - nov_1.weekday()) % 7)
    dst_end   = dst_end.replace(hour=6)
    return dst_start <= dt_utc < dst_end


def et_hour(dt_utc: datetime) -> int:
    offset = -4 if is_dst(dt_utc) else -5
    return (dt_utc.hour + offset) % 24


def check_et_time() -> bool:
    now_utc = datetime.now(timezone.utc)
    current_et_hour = et_hour(now_utc)
    if current_et_hour != TARGET_HOUR_ET:
        print(
            f"[send_email] Current ET hour is {current_et_hour}:xx - "
            f"not {TARGET_HOUR_ET} AM ET. Exiting silently."
        )
        return False
    return True


def get_latest_nav() -> dict:
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
    ticker = yf.Ticker(TICKER)
    try:
        price = ticker.fast_info["last_price"]
        if price and price > 0:
            return round(float(price), 2), "Yahoo Finance (last trade)"
    except Exception:
        pass
    hist = ticker.history(period="2d")
    if hist.empty:
        raise ValueError("Yahoo Finance returned no price data for PSUS.")
    price = round(float(hist["Close"].iloc[-1]), 2)
    price_date = hist.index[-1].strftime("%Y-%m-%d")
    return price, f"Yahoo Finance (close {price_date})"


def append_daily_price(price: float, discount: float) -> None:
    today_str = str(date.today())
    rows
