"""
Fetches the pieces of Powerball data that NY State's Open Data dataset
does NOT provide: current jackpot estimate, cash value, next drawing
date, and Double Play numbers/prize. These only exist as live-published
content on powerball.com - there is no public structured dataset for
them (confirmed by checking data.ny.gov's catalog directly).

This is intentionally narrow: it scrapes ONLY these specific values from
powerball.com's draw-result page, not the whole page. Keeping the scrape
target small minimizes how much can break if Powerball changes their
page layout, but doesn't eliminate that risk entirely - if this script
starts failing, the site's HTML structure has likely changed and the
selectors below need updating.

Writes data/powerball-jackpot.json, kept separate from data/powerball.json
(the NY Open Data output) since these come from a different, less stable
source and we don't want a scrape failure here to ever break the core
results pipeline.

NOTE ON TESTING: written without live network access to powerball.com
from this sandbox (outside the network allowlist). Selectors below are
based on the page's publicly visible structure as of early August 2026 -
run with --debug first and inspect the output before trusting a real run.
"""

import json
import os
import re
import sys
import datetime

import requests
from bs4 import BeautifulSoup

DRAW_RESULT_URL = "https://www.powerball.com/draw-result"
DOUBLE_PLAY_URL = "https://www.powerball.com/double-play"
OUTPUT_PATH = "data/powerball-jackpot.json"

REQUEST_TIMEOUT = 20


def fetch_page(url):
    resp = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": "Mozilla/5.0 (LottoPickHub jackpot fetch; contact: your-contact-email-here)",
            # explicitly exclude Brotli (br) -- requests can't auto-decompress it
            # without the optional 'brotli' package installed, which produced
            # garbled binary-looking text when the server sent br-encoded
            # content and we tried to read it as plain text
            "Accept-Encoding": "gzip, deflate",
        },
    )
    resp.raise_for_status()
    return resp.text


def parse_jackpot_and_cash_value(html, debug=False):
    """
    The draw-result page shows the estimated jackpot for the NEXT
    drawing alongside the most recent results. Looking for patterns
    like "Estimated Jackpot" and "Cash Value" near dollar figures.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    if debug:
        print("----- BEGIN PAGE TEXT (first 3000 chars) -----")
        print(text[:3000])
        print("----- END PAGE TEXT -----")

    jackpot_match = re.search(r"Estimated Jackpot\s*\$?([\d,.]+\s*(?:Million|Billion))", text, re.IGNORECASE)
    cash_match = re.search(r"Cash Value\s*\$?([\d,.]+\s*(?:Million|Billion))", text, re.IGNORECASE)

    return {
        "jackpot": f"${jackpot_match.group(1)}" if jackpot_match else None,
        "cash_value": f"${cash_match.group(1)}" if cash_match else None,
    }


def parse_next_drawing_date(html, debug=False):
    """
    Looking for the next scheduled drawing date, typically shown as a
    labeled date near "Next Drawing" text. Powerball draws Mon/Wed/Sat
    at 10:59pm ET - if this specific parse fails, next_drawing_date can
    be computed as a fallback from that fixed schedule instead of
    depending on the scrape (see compute_next_drawing_fallback below).
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    if debug:
        date_context = re.search(r".{0,80}Next Drawing.{0,80}", text, re.IGNORECASE)
        print(f"DEBUG: text around 'Next Drawing': {date_context.group() if date_context else 'NOT FOUND'}")

    date_match = re.search(
        r"Next Drawing.{0,40}?(\w+day,?\s+\w+\s+\d{1,2},?\s+\d{4})",
        text, re.IGNORECASE
    )
    if not date_match:
        return None

    date_str = re.sub(r"[^\w\s,]", "", date_match.group(1))
    for fmt in ("%A %B %d %Y", "%A, %B %d, %Y", "%B %d %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def compute_next_drawing_fallback(today=None):
    """
    Powerball draws every Mon/Wed/Sat at 10:59pm ET. If the scrape
    can't find an explicit date, compute the next one from this fixed
    schedule as a reliable fallback - this is public, unchanging
    information, not something that needs scraping at all.
    """
    today = today or datetime.date.today()
    draw_weekdays = {0, 2, 5}  # Monday, Wednesday, Saturday
    for offset in range(8):
        candidate = today + datetime.timedelta(days=offset)
        if candidate.weekday() in draw_weekdays:
            return candidate.isoformat()
    return None


def parse_double_play(html, debug=False):
    """
    Double Play numbers, when shown, appear as a labeled set of
    5 white balls + 1 red Powerball, separate from the main draw.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    if debug:
        context = re.search(r".{0,60}Double Play.{0,200}", text, re.IGNORECASE)
        print(f"DEBUG: text around 'Double Play': {context.group() if context else 'NOT FOUND'}")

    numbers_match = re.search(
        r"Double Play.{0,60}?(\d{1,2})[\s,-]+(\d{1,2})[\s,-]+(\d{1,2})[\s,-]+(\d{1,2})[\s,-]+(\d{1,2}).{0,30}?(\d{1,2})",
        text, re.IGNORECASE
    )
    if not numbers_match:
        return None

    numbers = [int(n) for n in numbers_match.groups()]
    return {
        "white_balls": sorted(numbers[:5]),
        "powerball": numbers[5],
    }


def main():
    debug = "--debug" in sys.argv

    result = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "jackpot": None,
        "cash_value": None,
        "next_drawing_date": None,
        "next_drawing_date_source": None,
        "double_play": None,
    }

    try:
        draw_result_html = fetch_page(DRAW_RESULT_URL)
        jackpot_info = parse_jackpot_and_cash_value(draw_result_html, debug=debug)
        result["jackpot"] = jackpot_info["jackpot"]
        result["cash_value"] = jackpot_info["cash_value"]

        next_date = parse_next_drawing_date(draw_result_html, debug=debug)
        if next_date:
            result["next_drawing_date"] = next_date
            result["next_drawing_date_source"] = "scraped"
        else:
            result["next_drawing_date"] = compute_next_drawing_fallback()
            result["next_drawing_date_source"] = "computed_from_schedule"
            print("Could not scrape next drawing date, using computed fallback from fixed Mon/Wed/Sat schedule")

        result["double_play"] = parse_double_play(draw_result_html, debug=debug)

    except requests.RequestException as e:
        print(f"Fetch failed: {e}", file=sys.stderr)
        result["next_drawing_date"] = compute_next_drawing_fallback()
        result["next_drawing_date_source"] = "computed_from_schedule"

    if debug:
        print("\n----- RESULT -----")
        print(json.dumps(result, indent=2))
        print("\nDebug mode: not writing output file. Re-run without --debug once this looks right.")
        return

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote jackpot data to {OUTPUT_PATH}")
    print(f"Jackpot: {result['jackpot']}, cash value: {result['cash_value']}, "
          f"next drawing: {result['next_drawing_date']} (source: {result['next_drawing_date_source']})")
    if result["double_play"]:
        print(f"Double Play: {result['double_play']}")
    else:
        print("Double Play: not found (may need selector adjustment)")


if __name__ == "__main__":
    main()
