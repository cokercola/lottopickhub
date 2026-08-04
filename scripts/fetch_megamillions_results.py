"""
Pulls Mega Millions drawing history from New York State's official Open
Data portal (data.ny.gov) - the same public government dataset pattern
used for scripts/update_powerball.py, just a different resource ID.

Endpoint: https://data.ny.gov/resource/5xaw-6ayf.json
Docs: https://dev.socrata.com/foundry/data.ny.gov/5xaw-6ayf

SCHEMA DIFFERENCE FROM POWERBALL: unlike the Powerball dataset, this one
does NOT embed the special ball inside "winning_numbers" - it's a
separate "mega_ball" field. "winning_numbers" here is only the 5 white
balls. parse_draw() below handles this.

FIELD NAMING NOTE: the output JSON still uses "powerball" as the key
for the Mega Ball value, and "red_ball_max" for its max value (24).
This is NOT a typo - it's deliberate, so that the existing generic
site.js / lottery-stats.js (written for Powerball first) can render
this page without any changes. Think of "powerball" in the JSON schema
as a generic "second-drum ball" field name inherited from the first
game built on this codebase, not a literal reference to Powerball.

KNOWN LIMITATION: same as Powerball - this dataset does NOT include
jackpot-win information. LAST_JACKPOT_DATE/AMOUNT below are manually-
maintained placeholders you update yourself when a jackpot is won
(megamillions.com announces this).

MATRIX HISTORY NOTE: Mega Millions changed its matrix multiple times.
The white ball range (1-70) has been stable since Oct 31, 2017, but the
Mega Ball range changed from 1-25 to 1-24 on Apr 8, 2025 (also when the
game added a built-in multiplier and raised the price to $5/play). To
keep EVERY stat in the history file valid - including "common Mega
Ball", which would be corrupted by pre-2025 draws that could roll a 25
- HISTORY_START_DATE is set to the more recent Apr 8, 2025 cutoff, not
the older Oct 2017 white-ball cutoff. This means much less historical
depth than Powerball (~130 draws vs ~1,700), because Mega Millions'
current matrix is only about 16 months old as of this writing.

Run on a schedule via .github/workflows/update-megamillions.yml

No API key required - this is a fully public dataset.
"""

import os
import json
import datetime
import requests

API_URL = "https://data.ny.gov/resource/5xaw-6ayf.json"
OUTPUT_PATH = "data/megamillions.json"
HISTORY_OUTPUT_PATH = "data/megamillions-history.json"

# MANUALLY UPDATE THIS when the jackpot changes (check megamillions.com).
# NY Open Data does NOT include forward-looking jackpot estimates or
# jackpot-win information - only confirmed historical draw results.
LAST_JACKPOT_DATE = "2026-07-28"
LAST_JACKPOT_AMOUNT = "$803,000,000"  # Florida, per megamillions.com

WHITE_BALL_COUNT = 5
WHITE_BALL_MAX = 70
RED_BALL_MAX = 24  # Mega Ball range as of the Apr 8, 2025 matrix change

# See MATRIX HISTORY NOTE above for why this is Apr 2025, not 2017.
HISTORY_START_DATE = "2025-04-08"


def fetch_all_draws():
    """Pulls the full drawing history. Mega Millions draws 2x/week and
    the dataset goes back to 2002, so this is a few thousand rows at
    most - well within a single request with a generous $limit."""
    params = {
        "$limit": 5000,
        "$order": "draw_date DESC",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_draw(record):
    """Parses one raw API record into our schema. Unlike Powerball,
    the Mega Ball is its own field ("mega_ball"), not embedded in
    winning_numbers - see the SCHEMA DIFFERENCE note above. If NY
    changes their schema, this is the first place to check -
    print(record) once to see the raw keys if this starts failing."""
    draw_date_raw = record.get("draw_date")
    winning_numbers_raw = record.get("winning_numbers")
    mega_ball_raw = record.get("mega_ball")
    multiplier_raw = record.get("multiplier")  # only present on older (pre-Apr 2025) records

    if not draw_date_raw or not winning_numbers_raw or not mega_ball_raw:
        return None

    draw_date = draw_date_raw[:10]

    parts = [int(n) for n in winning_numbers_raw.split()]
    if len(parts) != WHITE_BALL_COUNT:
        return None

    white_balls = sorted(parts)
    powerball = int(mega_ball_raw)  # see FIELD NAMING NOTE above

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
    (2025-04-08) to data/megamillions-history.json. Same purpose as
    Powerball's equivalent function: powers the client-side Hot & Cold
    dashboard, frequency heatmap, pair/triple analysis, historical
    draw explorer, and number lookup - all computed in the browser."""
    history_draws = [d for d in draws if d["draw_date"] >= HISTORY_START_DATE]
    history_draws.sort(key=lambda d: d["draw_date"])  # ascending, oldest first

    history_output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "since": HISTORY_START_DATE,
        "note": (
            "Only includes draws since the 2025-04-08 matrix change "
            "(5/70 + 1/24 Mega Ball). Earlier draws used a different "
            "Mega Ball range and are excluded to keep frequency stats "
            "valid. Much shorter history than Powerball's, since this "
            "matrix is far more recent."
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
            "name": "Mega Millions",
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
        "recent_draws": draws[:200],
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    write_history_file(draws)

    print(f"Wrote {len(draws)} total draws ({len(output['recent_draws'])} kept in output) "
          f"to {OUTPUT_PATH}")
    print(f"Latest draw: {latest['draw_date']} - {latest['white_balls']} + Mega Ball {latest['powerball']}")
    print(f"Stats since {LAST_JACKPOT_DATE}: {stats['draws_since_jackpot']} draws, "
          f"{len(stats['not_drawn'])} numbers not yet drawn")


if __name__ == "__main__":
    main()
