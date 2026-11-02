"""Merge the swipe game's answers back into the club table.

Inputs:  data/processed/world_clubs_located.csv   (locate_clubs.py)
         swipe/cards.json                          (build_swipe_decks.py; for the Overture/town points)
         swipe/swipe_decisions.csv                 (exported from the game; or pass another path)
Output:  data/processed/world_clubs_reviewed.csv  same columns, plus `swipe_review`, which lists every
         answer that touched a club (e.g. "ground:yes", "dupe:same_as:Q123"). The input is not changed.

What each answer does (later answers for the same card win; "skip" never changes anything):
  ground  yes   -> location = the Overture place; loc_method swipe_overture, loc_precision ground
          no    -> nothing changes (the club keeps its town point, or stays unlocated)
  dupe    same  -> one of the pair is flagged excluded, exclude_reason "duplicate_of:<kept id>".
                   Kept: the one with a ground-level location, then the one with more filled-in
                   fields, then the older Wikidata item. Its location is filled from the other if empty.
          diff  -> nothing changes
  youth   youth -> excluded, exclude_reason "youth_reserve_swipe"
          first -> the maybe_reserve_youth flag is removed
  town    <id>  -> location = that GeoNames town; loc_method swipe_town, loc_precision town
          none  -> nothing changes
Status and review_reason are then recomputed the same way as in locate_clubs.py.
Run from the project root:  python scripts/merge_swipe.py [path/to/swipe_decisions.csv]
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLUBS = ROOT / "data" / "processed" / "world_clubs_located.csv"
CARDS = ROOT / "swipe" / "cards.json"
DECISIONS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "swipe" / "swipe_decisions.csv"
OUT = ROOT / "data" / "processed" / "world_clubs_reviewed.csv"

d = pd.read_csv(CLUBS, dtype=str, keep_default_na=False).set_index("club", drop=False)
cards = {c["key"]: c for deck in json.load(open(CARDS, encoding="utf-8")).values() for c in deck}
dec = pd.read_csv(DECISIONS, dtype=str, keep_default_na=False)
dec = dec.sort_values("decided_at").drop_duplicates("key", keep="last")
dec = dec[dec["decision"] != "skip"]
d["swipe_review"] = ""
log = {}


def note(cid, text):
    d.at[cid, "swipe_review"] = (d.at[cid, "swipe_review"] + ";" + text).lstrip(";")


def set_loc(cid, lat, lon, method, precision, detail):
    d.loc[cid, ["loc_lat", "loc_lon", "loc_method", "loc_precision", "loc_detail"]] = \
        [str(lat), str(lon), method, precision, detail]


def filled(cid):
    return int((d.loc[cid] != "").sum())


for r in dec.itertuples():
    c = cards.get(r.key)
    if c is None:
        log["unknown card"] = log.get("unknown card", 0) + 1
        continue
    mode = r.key.split(":")[0]
    log[f"{mode}:{r.decision}"] = log.get(f"{mode}:{r.decision}", 0) + 1
    if mode == "ground":
        cid = c["club"]["id"]
        note(cid, "ground:" + r.decision)
        if r.decision == "yes":
            p = c["place"]
            set_loc(cid, p["lat"], p["lon"], "swipe_overture", "ground", p["name"])
    elif mode == "dupe":
        a, b = c["a"]["id"], c["b"]["id"]
        if r.decision != "same":
            note(a, "dupe:different_from:" + b), note(b, "dupe:different_from:" + a)
            continue
        rank = lambda x: (d.at[x, "loc_precision"] == "ground", filled(x), -int(x[1:]))
        keep, drop = (a, b) if rank(a) >= rank(b) else (b, a)
        if d.at[keep, "loc_lat"] == "" and d.at[drop, "loc_lat"] != "":
            set_loc(keep, *d.loc[drop, ["loc_lat", "loc_lon", "loc_method", "loc_precision", "loc_detail"]])
        d.at[drop, "status"] = "excluded"
        d.at[drop, "exclude_reason"] = "duplicate_of:" + keep
        note(keep, "dupe:kept_over:" + drop), note(drop, "dupe:same_as:" + keep)
    elif mode == "youth":
        cid = c["club"]["id"]
        note(cid, "youth:" + r.decision)
        if r.decision == "youth":
            d.at[cid, "status"] = "excluded"
            d.at[cid, "exclude_reason"] = "youth_reserve_swipe"
        elif r.decision == "first":
            d.at[cid, "review_reason"] = ";".join(
                x for x in d.at[cid, "review_reason"].split(";") if x and x != "maybe_reserve_youth")
    elif mode == "town":
        cid = c["club"]["id"]
        note(cid, "town:" + r.decision)
        t = next((t for t in c["towns"] if str(t["gid"]) == r.decision), None)
        if t:
            set_loc(cid, t["lat"], t["lon"], "swipe_town", "town", t["name"])

# recompute status for kept clubs (same rules as locate_clubs.py)
kept = d["status"] != "excluded"
weak = d["review_reason"].str.contains("maybe_reserve_youth")
parts = [("no_location", d["loc_lat"] == ""), ("no_country", d["country_iso"] == ""),
         ("no_name", d["name"] == ""), ("maybe_reserve_youth", weak)]
rr = pd.Series("", index=d.index)
for label, mask in parts:
    rr = rr.where(~mask, rr + ";" + label)
rr = rr.str.lstrip(";")
d.loc[kept, "review_reason"] = rr[kept]
d.loc[kept, "status"] = np.where(rr[kept] == "", "ok_for_mapping", "needs_review")

d.to_csv(OUT, index=False)
print("answers used:", json.dumps(log, indent=1))
print(d["status"].value_counts().to_string())
print(d.loc[d["status"] != "excluded", "loc_method"].replace("", "none").value_counts().to_string())
print("->", OUT)
