"""Merge the GeoBaller world Wikidata exports (data/incoming/world/world_*.csv) into one row per club.

Raw-first: nothing is dropped or cleaned. Where a club has several values (e.g. two venues),
they are joined with " | " in the same order across the paired columns (id | name | coord).
Output: data/processed/world_clubs_raw.csv
Run from the repo root:  python scripts/merge_world.py
"""
import re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "incoming" / "world"
OUT = ROOT / "data" / "processed" / "world_clubs_raw.csv"
SEP = " | "


def read(name):
    return pd.read_csv(IN / name, dtype=str, keep_default_na=False).drop_duplicates()


def qid(s):
    return s.str.replace("http://www.wikidata.org/entity/", "", regex=False)


def join(series):
    vals = [v for v in series if v != ""]
    return SEP.join(dict.fromkeys(vals))  # unique, order kept


def join_all(series):
    return SEP.join(series)  # keep position so paired columns line up


def point(s):
    # "POINT(lon lat)" -> (lat, lon)
    m = re.match(r"POINT\(([-\d.eE]+) ([-\d.eE]+)\)", s or "")
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)


def collapse(df, cols, how=join):
    return df.groupby("club", sort=False).agg({c: how for c in cols})


core = read("world_1_core.csv")
for c in ["club", "type", "country"]:
    core[c] = qid(core[c])
core["founded"] = core["founded"].str[:10]
core["dissolved"] = core["dissolved"].str[:10]
out = collapse(core, ["name_en", "type", "type_name", "country", "country_name", "founded", "dissolved"])

names = read("world_2_names.csv")
names["club"] = qid(names["club"])
wide = names.groupby(["club", "lang"])["name"].agg(join).unstack()
wide.columns = [f"name_{c}" for c in wide.columns]
out = out.join(wide)

co = read("world_3a_club_coords.csv")
co["club"] = qid(co["club"])
out = out.join(collapse(co, ["coord"]).rename(columns={"coord": "club_coord"}))

for fname, kind in [("world_3b_places.csv", "place"), ("world_3c_venues.csv", "venue")]:
    d = read(fname)
    d["club"] = qid(d["club"])
    d[kind] = qid(d[kind])
    out = out.join(collapse(d, [kind, f"{kind}_name", f"{kind}_coord"], how=join_all)
                   .rename(columns={kind: f"{kind}_id"}))

for fname in ["world_4a1_league_class_sport.csv", "world_4a2_merged_partof_owner.csv"]:
    d = read(fname)
    d["club"] = qid(d["club"])
    d["value"] = qid(d["value"])
    for field, g in d.groupby("field"):
        out = out.join(collapse(g, ["value", "value_name"], how=join_all)
                       .rename(columns={"value": f"{field}_id", "value_name": field}))

ln = read("world_4b_links.csv")
ln["club"] = qid(ln["club"])
ln["parent_club"] = qid(ln["parent_club"])
out = out.join(collapse(ln, ["parent_club", "transfermarkt_id"]).rename(columns={"parent_club": "parent_club_id"}))

out = out.fillna("")

# Single best point, picked in a fixed order: the club's own coordinate, then its first venue, then its first place.
def best(r):
    for col, src in [("club_coord", "club"), ("venue_coord", "venue"), ("place_coord", "place")]:
        for v in r[col].split(SEP):
            lat, lon = point(v)
            if lat is not None:
                return pd.Series([lat, lon, src])
    return pd.Series([None, None, ""])

out[["lat", "lon", "location_source"]] = out.apply(best, axis=1)

out["n_countries"] = out["country"].map(lambda s: len(s.split(SEP)) if s else 0)
out["n_types"] = out["type"].map(lambda s: len(s.split(SEP)) if s else 0)
out["wikidata_url"] = "https://www.wikidata.org/wiki/" + out.index

first = ["name_en", "country_name", "lat", "lon", "location_source", "type_name", "founded", "dissolved"]
out = out[first + [c for c in out.columns if c not in first]]
out.index.name = "club"
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, encoding="utf-8")
print(f"{len(out):,} clubs -> {OUT}")
