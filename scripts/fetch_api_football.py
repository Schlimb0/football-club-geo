"""Download every football league and its team list from API-Football (api-football.com, v3).

Free plan: 100 requests a day, 10 a minute. The script waits between calls, stops before the daily limit,
and skips anything already downloaded, so just run it again the next day to carry on.

Setup (once):
  1. Sign up at https://dashboard.api-football.com/register and copy your API key.
  2. Save the key in a file called  api_football_key.txt  in the Geoballer folder (NOT inside data/ or scripts/).
     Never share or commit this file.
Run from the Geoballer folder:
  python scripts/fetch_api_football.py
Only the Python standard library is used, so nothing needs installing.

Output (raw API answers, untouched):
  data/incoming/api_football/leagues.json                  one call: every league and cup
  data/incoming/api_football/teams/<league>_<season>.json  one call per league
  data/incoming/api_football/log.csv                       what was asked, when, and any error
"""
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY_FILE = ROOT / "api_football_key.txt"
OUT = ROOT / "data" / "incoming" / "api_football"
TEAMS = OUT / "teams"
BASE = "https://v3.football.api-sports.io"
DAILY_BUDGET = 95          # stay under the 100/day cap
PAUSE = 7                  # seconds between calls (10 a minute allowed)
MAX_SEASON = 2024          # the free plan only allows seasons 2022-2024
FALLBACK_SEASONS = [2023, 2022]
SKIP_WORDS = ("women", "female", "fem", "u17", "u18", "u19", "u20", "u21", "u23", "youth", "reserve", "futsal", "beach")


def get(path, key):
    req = urllib.request.Request(BASE + path, headers={"x-apisports-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        remaining = r.headers.get("x-ratelimit-requests-remaining")
        return json.load(r), remaining


def log(row):
    new = not (OUT / "log.csv").exists()
    with open(OUT / "log.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "request", "results", "errors", "remaining_today"])
        w.writerow(row)


def main():
    if not KEY_FILE.exists():
        sys.exit(f"Put your API key in {KEY_FILE} first (see the top of this script).")
    key = KEY_FILE.read_text().strip()
    TEAMS.mkdir(parents=True, exist_ok=True)
    remaining = None

    def call(path):
        # Stop BEFORE a call once the day's budget is used, so every answer we pay for gets saved.
        nonlocal remaining
        if remaining is not None and int(remaining) <= 100 - DAILY_BUDGET:
            print("Reached today's limit. Run again tomorrow to carry on.")
            sys.exit(0)
        data, left = get(path, key)
        if left not in (None, ""):
            remaining = left
        errors = data.get("errors") or ""
        log([datetime.now().isoformat(timespec="seconds"), path, data.get("results"), json.dumps(errors), left])
        time.sleep(PAUSE)
        return data, errors

    leagues_file = OUT / "leagues.json"
    if not leagues_file.exists():
        data, errors = call("/leagues")
        if errors:
            sys.exit(f"API error: {errors}")
        leagues_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"Saved {data['results']} leagues and cups.")
    leagues = json.loads(leagues_file.read_text(encoding="utf-8"))["response"]

    # Men's domestic leagues only (cups, women's, youth and reserve leagues skipped by name), top-ranked countries first.
    todo = []
    for item in leagues:
        lg, country = item["league"], item["country"]["name"]
        if lg["type"] != "League" or country == "World":
            continue
        if any(w in lg["name"].lower() for w in SKIP_WORDS):
            continue
        if not any(2022 <= s["year"] <= MAX_SEASON for s in item["seasons"]):
            continue  # no season the free plan can see (e.g. leagues only covered from 2025): don't spend a request
        current = [s["year"] for s in item["seasons"] if s.get("current")] or [max(s["year"] for s in item["seasons"])]
        todo.append((country, lg["id"], lg["name"], current[0]))
    todo.sort()
    done = {p.name.split("_")[0] for p in TEAMS.glob("*.json")}
    left = [t for t in todo if str(t[1]) not in done]
    print(f"{len(todo)} men's leagues in total, {len(todo) - len(left)} already downloaded, {len(left)} to go.")

    for country, lid, name, season in left:
        first = min(season, MAX_SEASON)
        for s in [first] + [y for y in FALLBACK_SEASONS if y < first]:
            data, errors = call(f"/teams?league={lid}&season={s}")
            if not errors:
                (TEAMS / f"{lid}_{s}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                print(f"{country}: {name} {s} -> {data['results']} teams")
                break
            print(f"{country}: {name} {s} -> not allowed ({errors}), trying an earlier season")
        else:
            print(f"{country}: {name} -> no season available on this plan")
    print("All leagues downloaded.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        sys.exit(f"Network problem: {e}. Check your connection and run again; nothing is lost.")
