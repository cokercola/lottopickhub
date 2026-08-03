"""
Pulls Powerball drawing history from New York State's official Open
Data portal (data.ny.gov) - a free, public government dataset, not a
scraper against powerball.com's HTML. This dataset goes back to 2010
and is maintained by NY State, updated as new drawings happen.

Endpoint: https://data.ny.gov/resource/d6yy-54nr.json
Docs: https://dev.socrata.com/foundry/data.ny.gov/d6yy-54nr

KNOWN LIMITATION: this dataset does NOT include jackpot-win
information (whether a given drawing produced a jackpot winner). The
"since last jackpot" feature therefore can't be computed from this
data alone. For now, LAST_JACKPOT_DATE below is a manually-maintained
placeholder you update yourself when you see news of a jackpot being
won (powerball.com announces this). A proper fix later would be
finding/scraping a jackpot-history source and wiring it in here
instead of hand-maintaining the date.

Also writes data/powerball-history.json: every draw since 2015-10-07
(the date Powerball moved to the current 5/69 + 1/26 matrix). Draws
before that date used a different number range, so they're excluded
to keep frequency/hot-cold/pair stats statistically valid. This file
powers the Hot & Cold dashboard, frequency heatmap, pair/triple
analysis, historical draw explorer, and number lookup pages.

Run on a schedule via .github/workflows/update-powerball.yml

No API key required - this is a fully public dataset.
"""

import os
import json
import datetime
import requests

API_URL = "https://data.ny.gov/resource/d6yy-54nr.json"
OUTPUT_PATH = "data/powerball.json"
HISTORY_OUTPUT_PATH = "data/powerball-history.json"

# MANUALLY UPDATE THIS when the jackpot changes (check powerball.com).
# NY Open Data does NOT include forward-looking jackpot estimates or
# jackpot-win information - only confirmed historical draw results -
# so there's no official feed for either of these. Rather than scrape
# a third-party site for a live dollar estimate (fragile - breaks
# whenever that site's layout changes), the homepage instead shows
# "growing since [this date]" without a dollar figure, computed
# directly from this one manually-maintained date.
LAST_JACKPOT_DATE = "2026-06-14"
LAST_JACKPOT_AMOUNT = "$412,000,000"  # also update manually alongside the date above

WHITE_BALL_COUNT = 5
WHITE_BALL_MAX = 69
RED_BALL_MAX = 26

# Current matrix (5/69 + 1/26) took effect this date. Draws before it
# used a different number range (5/59 + 1/35) and can't be mixed into
# frequency/hot-cold/pair stats without corrupting them.
HISTORY_START_DATE = "2015-10-07"


def fetch_all_draws():
    """Pulls the full drawing history. The dataset only goes back to
    2010 and Powerball draws 2-3x/week, so this is a few thousand rows
    at most - well within a single request with a generous $limit."""
    params = {
        "$limit": 5000,
        "$order": "draw_date DESC",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_draw(record):
    """Parses one raw API record into our schema. Socrata's field
    naming convention lowercases and underscores the display name, so
    "Draw Date" -> "draw_date" and "Winning Numbers" -> "winning_numbers".
    If NY changes their schema, this is the first place to check -
    print(record) once to see the raw keys if this starts failing."""
    draw_date_raw = record.get("draw_date")
    winning_numbers_raw = record.get("winning_numbers")
    multiplier_raw = record.get("multiplier")

    if not draw_date_raw or not winning_numbers_raw:
        return None

    # draw_date comes back as an ISO timestamp like "2026-06-17T00:00:00.000"
    draw_date = draw_date_raw[:10]

    # winning_numbers is a space-separated string of all 6 numbers,
    # with the Powerball itself as the LAST number in the string.
    parts = [int(n) for n in winning_numbers_raw.split()]
    if len(parts) != WHITE_BALL_COUNT + 1:
        return None

    white_balls = sorted(parts[:WHITE_BALL_COUNT])
    powerball = parts[WHITE_BALL_COUNT]

    return {
        "draw_date": draw_date,
        "white_balls": white_balls,
        "powerball": powerball,
        "multiplier": multiplier_raw,
    }


def compute_stats(draws, since_date):
    """Most-drawn and not-drawn white ball counts since `since_date`
    (inclusive). Only counts draws on/after that date."""
    relevant = [d for d in draws if d["draw_date"] >= since_date]

    counts = {n: 0 for n in range(1, WHITE_BALL_MAX + 1)}
    for d in relevant:
        for n in d["white_balls"]:
            counts[n] = counts.get(n, 0) + 1

    most_drawn = sorted(
        [{"number": n, "count": c} for n, c in counts.items() if c > 0],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    not_drawn = sorted([n for n, c in counts.items() if c == 0])

    return {
        "draws_since_jackpot": len(relevant),
        "most_drawn": most_drawn,
        "not_drawn": not_drawn,
    }


def write_history_file(draws):
    """Writes every draw since the current matrix took effect
    (2015-10-07) to data/powerball-history.json. This powers the
    client-side Hot & Cold dashboard, frequency heatmap, pair/triple
    analysis, historical draw explorer, and number lookup pages - all
    computed in the browser from this one file rather than
    precomputed here, since ~1,700 draws is small enough for the
    browser to crunch instantly and it keeps this script simple as
    more features get added on the frontend."""
    history_draws = [d for d in draws if d["draw_date"] >= HISTORY_START_DATE]
    history_draws.sort(key=lambda d: d["draw_date"])  # ascending, oldest first

    history_output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "since": HISTORY_START_DATE,
        "note": (
            "Only includes draws since the 2015-10-07 matrix change "
            "(5/69 + 1/26). Earlier draws used a different number "
            "range and are excluded to keep frequency stats valid."
        ),
        "draws": [
            {
                "draw_date": d["draw_date"],
                "white_balls": d["white_balls"],
                "powerball": d["powerball"],
            }
            for d in history_draws
        ],
    }

    with open(HISTORY_OUTPUT_PATH, "w") as f:
        json.dump(history_output, f, indent=2)

    print(f"Wrote {len(history_draws)} draws since {HISTORY_START_DATE} to {HISTORY_OUTPUT_PATH}")


def main():
    raw_draws = fetch_all_draws()
    draws = [parse_draw(r) for r in raw_draws]
    draws = [d for d in draws if d is not None]

    if not draws:
        raise RuntimeError(
            "No valid draws parsed from the API response - the dataset's "
            "field names may have changed. Check a raw record's keys."
        )

    draws.sort(key=lambda d: d["draw_date"], reverse=True)
    latest = draws[0]

    stats = compute_stats(draws, LAST_JACKPOT_DATE)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "game": {
            "name": "Powerball",
            "white_ball_count": WHITE_BALL_COUNT,
            "white_ball_max": WHITE_BALL_MAX,
            "red_ball_max": RED_BALL_MAX,
        },
        "latest_draw": latest,
        "last_jackpot": {
            "date": LAST_JACKPOT_DATE,
            "amount": LAST_JACKPOT_AMOUNT,
            "note": "Manually maintained - see script docstring.",
        },
        "stats_since_jackpot": stats,
        # Keep a reasonable amount of recent history for the archive
        # search feature, without bloating the JSON file with 15 years
        # of data on every page load.
        "recent_draws": draws[:200],
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    write_history_file(draws)

    print(f"Wrote {len(draws)} total draws ({len(output['recent_draws'])} kept in output) "
          f"to {OUTPUT_PATH}")
    print(f"Latest draw: {latest['draw_date']} - {latest['white_balls']} + PB {latest['powerball']}")
    print(f"Stats since {LAST_JACKPOT_DATE}: {stats['draws_since_jackpot']} draws, "
          f"{len(stats['not_drawn'])} numbers not yet drawn")


if __name__ == "__main__":
    main()
