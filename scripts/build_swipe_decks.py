"""Build the four card decks for the club review swipe game.

Inputs:  data/processed/world_clubs_located.csv  (locate_clubs.py)
         data/processed/overture_matches.csv     (match_overture.py)
         GeoNames towns with 500+ people         (pip install geonamescache; CC-BY 4.0)
Output:  swipe/cards.json   one list of cards per mode:
  ground  "Is this the club's ground?"  iffy Overture matches for clubs with no location
          or only a town-level one (the swipe could upgrade them to a ground point)
  dupe    "Same club?"   two kept clubs with the same name in the same country
  youth   "First team or youth/reserve?"  names with Academy/Youth/Primavera... words
  town    "Which town?"  clubs whose name fits more than one GeoNames town
Run from the project root:  python scripts/build_swipe_decks.py
"""
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
import pandas as pd
import geonamescache

ROOT = Path(__file__).resolve().parent.parent
CLUBS = ROOT / "data" / "processed" / "world_clubs_located.csv"
OVERTURE = ROOT / "data" / "processed" / "overture_matches.csv"
OUT = ROOT / "swipe" / "cards.json"
MAX_TOWNS = 8  # towns shown on one card, biggest first

# same word list as locate_clubs.py, so the town candidates are the same
STOP = set("""fc cf sc sv fk sk ac as cd ud ad club clube klub football futbol futebol calcio soccer
united city town athletic atletico sporting sport sports association real deportivo esporte rovers
wanderers rangers celtic albion county the and union olympic olympique dynamo dinamo spartak lokomotiv
academy youth juniors santos internacional nacional independiente estrella star stars""".split())


def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower().replace("ß", "ss"))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def km(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return round(12742 * math.asin(math.sqrt(x)), 1)


def num(x):
    try:
        return round(float(x), 5)
    except (TypeError, ValueError):
        return None


d = pd.read_csv(CLUBS, dtype=str, keep_default_na=False)
k = d[d["status"] != "excluded"].copy()
by_id = k.set_index("club")


def club(r):
    """The facts shown about one club on a card (empty fields left out)."""
    f = {
        "id": r.name if isinstance(r.name, str) else r["club"], "name": r["name"], "name_en": r["name_en"],
        "country": r["country_name"].split(" | ")[0], "type": r["type_name"],
        "founded": r["founded"][:4], "dissolved": r["dissolved"][:4], "league": r["league"],
        "venue": r["venue_name"], "place": r["place_name"], "parent": r["part_of"] or r["owned_by"],
        "lat": num(r["loc_lat"]), "lon": num(r["loc_lon"]), "loc_method": r["loc_method"],
        "loc_precision": r["loc_precision"], "loc_detail": r["loc_detail"], "tm": r["transfermarkt_id"],
    }
    if f["name_en"] == f["name"]:
        f["name_en"] = ""
    return {a: b for a, b in f.items() if b not in ("", None)}


cards = {}

# --- ground: iffy Overture matches ---------------------------------------------------------------
ov = pd.read_csv(OVERTURE, dtype=str, keep_default_na=False)
ov = ov[(ov["match_type"] == "iffy") & ov["club"].isin(by_id.index)]
deck = []
for o in ov.itertuples():
    r = by_id.loc[o.club]
    if r["loc_method"] not in ("", "geonames_town"):
        continue  # already has a Wikidata or exact point: a fuzzy match can't improve it
    c = {"key": "ground:" + o.club, "club": club(r),
         "place": {"name": o.ov_name, "category": o.ov_category, "locality": o.ov_locality,
                   "lat": num(o.ov_lat), "lon": num(o.ov_lon), "website": o.ov_website,
                   "score": int(float(o.score or 0)), "confidence": round(float(o.ov_confidence or 0), 2)},
         "others": [x for x in o.candidates.split(" | ")[1:] if x]}
    if c["club"].get("lat") is not None and c["place"]["lat"] is not None:
        c["km"] = km(c["club"]["lat"], c["club"]["lon"], c["place"]["lat"], c["place"]["lon"])
    deck.append(c)
cards["ground"] = deck

# --- dupe: same name, same country --------------------------------------------------------------
k["nkey"] = k["name"].map(lambda s: re.sub(r"[^a-z0-9]+", " ", norm(s)).strip())
named = k[(k["nkey"] != "") & (k["country_iso"] != "")]
deck = []
for (_, cc), g in named.groupby(["nkey", "country_iso"]):
    if len(g) < 2:
        continue
    g = g.sort_values("club", key=lambda s: s.str[1:].astype(int))  # oldest Wikidata item first
    first = g.iloc[0]
    for _, other in g.iloc[1:].iterrows():
        a, b = club(first.rename(first["club"])), club(other.rename(other["club"]))
        c = {"key": f"dupe:{a['id']}:{b['id']}", "a": a, "b": b, "group": len(g)}
        if a.get("lat") is not None and b.get("lat") is not None:
            c["km"] = km(a["lat"], a["lon"], b["lat"], b["lon"])
        deck.append(c)
cards["dupe"] = deck

# --- youth: softer youth/reserve words ----------------------------------------------------------
y = k[k["review_reason"].str.contains("maybe_reserve_youth")]
cards["youth"] = [{"key": "youth:" + r["club"], "club": club(r.rename(r["club"]))} for _, r in y.iterrows()]

# --- town: several GeoNames towns fit the name -------------------------------------------------
gc = geonamescache.GeonamesCache(min_city_population=500)
towns = pd.DataFrame(gc.get_cities().values())
idx = defaultdict(set)
for r in towns.itertuples():
    for n in {r.name, *r.alternatenames}:
        idx[(r.countrycode, norm(n))].add(r.Index)


def town_for(name, cc):
    w = re.findall(r"[\w'\-]+", norm(name))
    for size in (3, 2, 1):
        hits = set()
        for i in range(len(w) - size + 1):
            g = w[i:i + size]
            if size == 1 and (g[0] in STOP or len(g[0]) < 3 or g[0].isdigit()):
                continue
            hits |= idx.get((cc, " ".join(g)), set())
        if hits:
            return hits
    return set()


big = towns[towns["population"] >= 100000].reset_index(drop=True)


def near_city(lat, lon, cc):
    """Nearest city of 100k+ people in the same country, to tell same-named towns apart."""
    b = big[big["countrycode"] == cc]
    if b.empty:
        return ""
    dist = [km(lat, lon, a, o) for a, o in zip(b["latitude"], b["longitude"])]
    i = min(range(len(dist)), key=dist.__getitem__)
    return "in " + b.iloc[i]["name"] if dist[i] < 5 else f"{round(dist[i])} km from {b.iloc[i]['name']}"


t = k[(k["loc_lat"] == "") & (k["town_candidates"].astype(int) > 1)]
deck = []
for _, r in t.iterrows():
    hits = towns.loc[list(town_for(r["name"], r["country_iso"]))].sort_values("population", ascending=False)
    opts = [{"gid": int(h.geonameid), "name": h["name"], "near": near_city(float(h.latitude), float(h.longitude), h.countrycode), "pop": int(h.population),
             "lat": round(float(h.latitude), 5), "lon": round(float(h.longitude), 5)}
            for _, h in hits.head(MAX_TOWNS).iterrows()]
    deck.append({"key": "town:" + r["club"], "club": club(r.rename(r["club"])), "towns": opts,
                 "n_towns": len(hits)})
cards["town"] = deck

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(cards, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
for m, v in cards.items():
    print(f"{m:7s} {len(v):5d} cards")
print("size", round(OUT.stat().st_size / 1e6, 2), "MB ->", OUT)
