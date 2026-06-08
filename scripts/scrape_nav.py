"""
scrape_nav.py
-------------
Runs every Wednesday via GitHub Actions.
Scrapes the latest NAV from pershingsquareusa.com/performance/
and appends it to the CSV database if it is new.
"""

import requests
from bs4 import BeautifulSoup
import csv
import os
import re
import sys
from datetime import datetime, date

NAV_URL = "https://www.pershingsquareusa.com/performance/"
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "psus_nav_database.csv")

CURRENT_YEAR = date.today().year


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_nav_entries(html: str) -> list[dict]:
    """
    Parse NAV table entries from the PSUS performance page.
    The page renders data as <li> elements in this repeating order:
      date | period | NAV/share | NYSE Px/share | ...
    We collect every group that contains a recognisable date.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = [li.get_text(strip=True) for li in soup.find_all("li")]

    entries = []
    i = 0
    while i < len(items):
        # Match a date like "31 May" or "5 May"
        if re.match(r"^\d{1,2}\s+[A-Za-z]+$", items[i]):
            try:
                raw_date  = items[i]          # "31 May"
                period    = items[i + 1]      # "Weekly" / "Monthly" / "IPO Price"
                nav_str   = items[i + 2]      # "$48.93"
                nyse_str  = items[i + 3]      # "$40.13"

                nav_value  = float(nav_str.replace("$", "").replace(",", ""))
                nyse_value = float(nyse_str.replace("$", "").replace(",", ""))

                nav_date = datetime.strptime(
                    f"{raw_date} {CURRENT_YEAR}", "%d %B %Y"
                ).date()

                entries.append({
                    "date":   str(nav_date),
                    "period": period,
                    "nav":    nav_value,
                    "nyse":   nyse_value,
                })
                i += 4
                continue
            except (IndexError, ValueError):
                pass
        i += 1

    return entries


def load_existing_dates(csv_path: str) -> set:
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return {row["date"] for row in reader}


def append_to_csv(csv_path: str, entry: dict) -> None:
    discount = round((entry["nyse"] / entry["nav"] - 1) * 100, 2)
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            entry["date"],
            entry["period"],
            entry["nav"],
            entry["nyse"],
            discount,
        ])


def main() -> None:
    print(f"[scrape_nav] Running on {date.today()}")

    html = fetch_page(NAV_URL)
    entries = parse_nav_entries(html)

    if not entries:
        print("[scrape_nav] ERROR: No NAV entries parsed — page layout may have changed.")
        sys.exit(1)

    existing_dates = load_existing_dates(CSV_PATH)
    new_entries = [e for e in entries if e["date"] not in existing_dates]

    if not new_entries:
        print(f"[scrape_nav] No new entries found. Latest on page: {entries[0]['date']}")
        return

    for entry in sorted(new_entries, key=lambda x: x["date"]):
        append_to_csv(CSV_PATH, entry)
        discount = round((entry["nyse"] / entry["nav"] - 1) * 100, 2)
        print(
            f"[scrape_nav] Added {entry['date']} | {entry['period']} | "
            f"NAV ${entry['nav']:.2f} | NYSE ${entry['nyse']:.2f} | "
            f"Discount {discount:+.2f}%"
        )


if __name__ == "__main__":
    main()
