"""Match clubs to Overture Maps places to get their actual location (ground / clubhouse).

Inputs:  data/processed/world_clubs_flagged.csv           (from flag_clubs.py)
         data/incoming/overture/overture_football_places.csv (from fetch_overture_football.py)
Output:  data/processed/overture_matches.csv  - one row per club that was not excluded:
           match_type  exact_wikidata | exact_name | iffy | none
           ov_*        the chosen Overture place (name, category, lat, lon, ...)
           n_candidates, score, candidates (top 3 for the swipe game)

Rules
  exact_wikidata  the Overture place carries the club's own Wikidata id
  exact_name      after removing generic words (FC, SC, club, football ...) and accents, the club's
                  name equals the place name, in the same country, and every place with that name
                  in the country lies within 2 km of the others (so it is one ground)
  iffy            a close but not identical name (similarity >= 85/100), or an identical name that
                  points at places more than 2 km apart
  none            nothing close enough
Run from the project root:  python scripts/match_overture.py
"""
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parent.parent
CLUBS = ROOT / "data" / "processed" / "world_clubs_flagged.csv"
PLACES = ROOT / "data" / "incoming" / "overture" / "overture_football_places.csv"
OUT = ROOT / "data" / "processed" / "overture_matches.csv"
FUZZY_MIN = 85
SAME_GROUND_KM = 2.0

# Wikidata country name -> ISO code, for names the GeoNames list spells differently
COUNTRY_FIX = {
    "Netherlands": "NL", "Kingdom of the Netherlands": "NL", "Czech Republic": "CZ",
    "People's Republic of China": "CN", "Cape Verde": "CV", "Palestine": "PS", "Timor-Leste": "TL",
    "São Tomé and Príncipe": "ST", "The Gambia": "GM", "The Bahamas": "BS", "Curaçao": "CW",
    "Wales": "GB", "Northern Ireland": "GB", "England": "GB", "Scotland": "GB", "Macau": "MO",
    "Federated States of Micronesia": "FM", "United States Virgin Islands": "VI", "Vatican City": "VA",
    "Réunion": "RE", "Kingdom of Denmark": "DK", "Northern Cyprus": "CY",
}

GENERIC = set("""fc f c afc a sc s cf cd ud ad sd club clube klub klubi kulubu football futbol futebol
fussball fusball voetbal fotball fotboll fodbold calcio soccer association asociacion associacao
sport sports sporting spor sportverein sv tsv vfb vfl fsv fk nk sk ks tj jk ik if bk gks ac as us ss
asd usd ssd ec esporte the de del la le los las el do da di des du und and of team united""".split())


def iso_lookup():
    import geonamescache
    m = {v["name"]: k for k, v in geonamescache.GeonamesCache().get_countries().items()}
    m.update(COUNTRY_FIX)
    return m


def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower().replace("ß", "ss"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", s)
    core = [w for w in words if w not in GENERIC]
    return " ".join(core)


def km(a, b, c, d):
    p = math.pi / 180
    x = (math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(x))


def spread_km(rows):
    pts = list(zip(rows["lat"], rows["lon"]))
    return max((km(*p, *q) for p in pts for q in pts), default=0.0)


clubs = pd.read_csv(CLUBS, dtype=str, keep_default_na=False)
clubs = clubs[clubs["status"] != "excluded"].copy()
iso = iso_lookup()
clubs["iso"] = clubs["country_name"].str.split(" | ", regex=False).str[0].map(iso).fillna("")
clubs["key"] = clubs["name"].map(norm)

pl = pd.read_csv(PLACES, dtype={"wikidata": str}, keep_default_na=False)
pl = pl[(pl["lat"] != 0) | (pl["lon"] != 0)]
# only places that are clearly about sport: a sports category, or a football word in the name
# (stops "US Saint-Omer" matching an insurance agency called "Saint Omer")
SPORT_CAT = r"sport|soccer|football|stadium|arena|athlet|club|league|field|recreation"
FOOT_WORD = (r"\b(?:f\.?\s?c|a\.?f\.?c|s\.?c|football|soccer|f[uú]tbol|futebol|calcio|fu(?:ss|ß)ball|voetbal|"
             r"fotball|fotboll|fodbold|futbal|fudbal|nogomet|sv|tsv|vfb|vfl|fk|nk|sk|ks|cd|ud|ss|asd|usd)\b")
pl = pl[pl["category"].str.contains(SPORT_CAT, case=False) | pl["basic_category"].str.contains(SPORT_CAT, case=False)
        | pl["name"].str.contains(FOOT_WORD, case=False, regex=True)]
pl["key"] = pl["name"].map(norm)
pl = pl[pl["key"].str.len() >= 3]
by_wd = pl[pl["wikidata"] != ""].drop_duplicates("wikidata").set_index("wikidata")
by_country = {cc: g.reset_index(drop=True) for cc, g in pl.groupby("country")}
by_country_key = {cc: g.groupby("key").indices for cc, g in by_country.items()}
# word index: only places sharing a word with the club name are compared in the fuzzy step
by_country_word = {}
for cc, g in by_country.items():
    idx = defaultdict(list)
    for i, k in enumerate(g["key"]):
        for w in set(k.split()):
            if len(w) >= 3:
                idx[w].append(i)
    by_country_word[cc] = idx

out = []
for r in clubs.itertuples():
    rec = {"club": r.club, "match_type": "none", "n_candidates": 0, "score": "", "candidates": ""}
    best = None
    if r.club in by_wd.index:
        best = by_wd.loc[r.club]
        rec.update(match_type="exact_wikidata", n_candidates=1, score=100)
    elif r.key and len(r.key) >= 3 and r.iso in by_country:
        places = by_country[r.iso]
        hits = by_country_key[r.iso].get(r.key)
        if hits is not None:
            g = places.iloc[hits]
            best = g.sort_values("confidence", ascending=False).iloc[0]
            same = spread_km(g.head(20)) <= SAME_GROUND_KM
            rec.update(match_type="exact_name" if same else "iffy", n_candidates=len(g), score=100)
        else:
            pool = sorted({i for w in r.key.split() if len(w) >= 3
                           for i in by_country_word[r.iso].get(w, [])})
            sub = places.iloc[pool] if pool else places.iloc[[]]
            cands = process.extract(r.key, dict(zip(sub.index, sub["key"])), scorer=fuzz.token_sort_ratio,
                                    score_cutoff=FUZZY_MIN, limit=3)
            if cands:
                best = places.iloc[cands[0][2]]
                rec.update(match_type="iffy", n_candidates=len(cands), score=round(cands[0][1]),
                           candidates=" | ".join(places.iloc[c[2]]["name"] for c in cands))
    if best is not None:
        for c in ["overture_id", "name", "category", "locality", "lat", "lon", "confidence", "website"]:
            rec["ov_" + c] = best[c]
    out.append(rec)

res = pd.DataFrame(out)
res.to_csv(OUT, index=False)
print(res["match_type"].value_counts().to_string())
