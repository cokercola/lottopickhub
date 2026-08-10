"""
Pulls NY Pick 3 (branded "Numbers" by NY Lottery) drawing history from
New York State's official Open Data portal (data.ny.gov) - same
Socrata platform already used by fetch_powerball_results.py, just a
different dataset.

Dataset: "Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980"
Catalog page: https://data.ny.gov/d/hsys-3def
Likely JSON endpoint (Socrata convention - same pattern as the
Powerball dataset's d6yy-54nr): https://data.ny.gov/resource/hsys-3def.json

IMPORTANT - VERIFY BEFORE RELYING ON THIS SCRIPT:
This dataset combines TWO games (Numbers/Pick 3 AND Win 4) in one
table, with separate midday and evening draws each day. The exact
field names below (MIDDAY_FIELD, EVENING_FIELD, etc.) are Socrata's
usual "lowercase + underscore the display name" convention applied to
what the catalog page shows, but they have NOT been confirmed against
a live API response in this session. Before running on a schedule:
  1. Run this script once locally / manually.
  2. If it errors or the digits look wrong, uncomment the debug print
     in fetch_all_draws() below to see the raw field names Socrata
     actually returns, and fix the *_FIELD constants to match.
This same caveat doesn't apply to fetch_powerball_results.py, whose
field names were already confirmed working - only this Pick 3 version
is new and needs that one-time check.

Only pulls the Numbers (Pick 3) columns - Win 4 columns in the same
dataset are ignored.

Writes data/pick3/ny-history.json in the shape pick3-stats.js expects:
  { updated_at, state: "ny", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [h,t,o], fireball: null }
  ]}
NY's Numbers game does not have a Fireball-style bonus digit, so
fireball is always null for this state - the front-end already
handles that (hasFireball: false in PICK3_STATES).

Run on a schedule via .github/workflows/update-pick3-ny.yml (create
following the same pattern as update-powerball.yml).
"""

import os
import json
import datetime
import requests

API_URL = "https://data.ny.gov/resource/hsys-3def.json"
OUTPUT_PATH = "data/pick3/ny-history.json"

# Best-guess Socrata field names - VERIFY, see docstring above.
DRAW_DATE_FIELD = "draw_date"
MIDDAY_FIELD = "midday_daily"
EVENING_FIELD = "evening_daily"

# How far back to keep. NY's dataset goes back to 1980, but that's far
# more than needed for hot/cold or heatmap stats and would bloat the
# JSON file for no benefit - keep the last ~2 years of draws instead.
# Adjust freely; there's no "matrix change" cutoff to worry about here
# since Pick 3's 0-9 digit range has never changed.
KEEP_SINCE_YEARS = 2


def fetch_all_draws():
    since = (datetime.date.today() - datetime.timedelta(days=365 * KEEP_SINCE_YEARS)).isoformat()
    params = {
        "$limit": 5000,
        "$order": f"{DRAW_DATE_FIELD} DESC",
        "$where": f"{DRAW_DATE_FIELD} >= '{since}T00:00:00.000'",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    records = resp.json()

    # Uncomment to inspect real field names if parsing comes up empty:
    # if records:
    #     print(json.dumps(records[0], indent=2))

    return records


def parse_digits(raw):
    """NY's Numbers value is typically a 3-character string like "472"
    (sometimes zero-padded, sometimes not - handle both). Returns None
    if the field is missing/blank (some early rows or skipped draws)."""
    if not raw:
        return None
    cleaned = str(raw).strip().zfill(3)
    if len(cleaned) != 3 or not cleaned.isdigit():
        return None
    return [int(c) for c in cleaned]


def parse_record(record):
    draw_date_raw = record.get(DRAW_DATE_FIELD)
    if not draw_date_raw:
        return []

    draw_date = draw_date_raw[:10]
    out = []

    midday_digits = parse_digits(record.get(MIDDAY_FIELD))
    if midday_digits:
        out.append({"draw_date": draw_date, "draw_time": "midday", "digits": midday_digits, "fireball": None})

    evening_digits = parse_digits(record.get(EVENING_FIELD))
    if evening_digits:
        out.append({"draw_date": draw_date, "draw_time": "evening", "digits": evening_digits, "fireball": None})

    return out


def main():
    raw_records = fetch_all_draws()

    draws = []
    for r in raw_records:
        draws.extend(parse_record(r))

    if not draws:
        raise RuntimeError(
            "No valid Pick 3 draws parsed - the dataset's field names may "
            "not match MIDDAY_FIELD/EVENING_FIELD. Uncomment the debug "
            "print in fetch_all_draws() and check the raw keys."
        )

    draws.sort(key=lambda d: (d["draw_date"], d["draw_time"]))  # ascending, oldest first

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "ny",
        "note": f"Last {KEEP_SINCE_YEARS} years of NY Numbers (Pick 3) draws. NY has no Fireball-equivalent bonus digit.",
        "draws": draws,
    }

    os.makedirs("data/pick3", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(draws)} draws to {OUTPUT_PATH}")
    print(f"Latest: {draws[-1]['draw_date']} {draws[-1]['draw_time']} - {draws[-1]['digits']}")


if __name__ == "__main__":
    main()
