"""Give every kept club the best location we have, and tag how it was found.

Inputs:  data/processed/world_clubs_flagged.csv   (flag_clubs.py)
         data/processed/overture_matches.csv       (match_overture.py)
         GeoNames towns with 500+ people            (pip install geonamescache; CC-BY 4.0)
Output:  data/processed/world_clubs_located.csv    all clubs, with these new columns:

  loc_lat, loc_lon      the location to use
  loc_method            where it came from, best first:
                          wikidata_club   the club's own Wikidata coordinates
                          wikidata_venue  its home ground's Wikidata coordinates
                          wikidata_place  the Wikidata town/area it is "located in"
                          overture_exact  an exact name match in Overture Maps (CDLA-Permissive-2.0)
                          geonames_town   a town named in the club's name, found in GeoNames (CC-BY 4.0)
  loc_precision         ground (club/venue/Overture) or town (Wikidata place, GeoNames)
  loc_detail            Overture place name, or GeoNames town name
  country_iso           ISO code of the club's country
  country_method        wikidata, or nearest_town (filled from the nearest GeoNames town
                        to the club's coordinates, when Wikidata gives no country)
  status / review_reason are recomputed: a club that now has a location is ok_for_mapping
  unless something else is missing.
Excluded clubs keep status "excluded" and get no new location.
Run from the project root:  python scripts/locate_clubs.py
"""
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import geonamescache

ROOT = Path(__file__).resolve().parent.parent
CLUBS = ROOT / "data" / "processed" / "world_clubs_flagged.csv"
OVERTURE = ROOT / "data" / "processed" / "overture_matches.csv"
OUT = ROOT / "data" / "processed" / "world_clubs_located.csv"

COUNTRY_FIX = {
    "Netherlands": "NL", "Kingdom of the Netherlands": "NL", "Czech Republic": "CZ",
    "People's Republic of China": "CN", "Cape Verde": "CV", "Palestine": "PS", "Timor-Leste": "TL",
    "São Tomé and Príncipe": "ST", "The Gambia": "GM", "The Bahamas": "BS", "Curaçao": "CW",
    "Wales": "GB", "Northern Ireland": "GB", "England": "GB", "Scotland": "GB", "Macau": "MO",
    "Federated States of Micronesia": "FM", "United States Virgin Islands": "VI", "Vatican City": "VA",
    "Réunion": "RE", "Kingdom of Denmark": "DK", "Northern Cyprus": "CY",
}
# words that are never a town, even if a tiny place has that name
STOP = set("""fc cf sc sv fk sk ac as cd ud ad club clube klub football futbol futebol calcio soccer
united city town athletic atletico sporting sport sports association real deportivo esporte rovers
wanderers rangers celtic albion county the and union olympic olympique dynamo dinamo spartak lokomotiv
academy youth juniors santos internacional nacional independiente estrella star stars""".split())

gc = geonamescache.GeonamesCache(min_city_population=500)
countries = gc.get_countries()
iso_of = {v["name"]: k for k, v in countries.items()}
iso_of.update(COUNTRY_FIX)
towns = pd.DataFrame(gc.get_cities().values())


def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower().replace("ß", "ss"))
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def first_point(s):
    m = re.match(r"POINT\(([-\d.eE]+) ([-\d.eE]+)\)", s or "")
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)


d = pd.read_csv(CLUBS, dtype=str, keep_default_na=False)
kept = d["status"] != "excluded"

# --- 1. existing Wikidata location, split by its source -----------------------------------------
d["loc_lat"], d["loc_lon"], d["loc_method"], d["loc_precision"], d["loc_detail"] = "", "", "", "", ""
has = d["lat"] != ""
src = d["location_source"].map({"club": "wikidata_club", "venue": "wikidata_venue", "place": "wikidata_place"})
d.loc[has, ["loc_lat", "loc_lon"]] = d.loc[has, ["lat", "lon"]].values
d.loc[has, "loc_method"] = src[has].fillna("wikidata")
d.loc[has, "loc_precision"] = np.where(d.loc[has, "loc_method"] == "wikidata_place", "town", "ground")

# --- 2. Overture exact matches ------------------------------------------------------------------
ov = pd.read_csv(OVERTURE, dtype=str, keep_default_na=False).set_index("club")
ov = ov[ov["match_type"].isin(["exact_wikidata", "exact_name"])]
take = kept & ~has & d["club"].isin(ov.index)
o = ov.loc[d.loc[take, "club"]]
d.loc[take, "loc_lat"] = o["ov_lat"].values
d.loc[take, "loc_lon"] = o["ov_lon"].values
d.loc[take, "loc_method"] = "overture_exact"
d.loc[take, "loc_precision"] = "ground"
d.loc[take, "loc_detail"] = (o["ov_name"] + " (" + o["ov_category"] + ")").values

# --- 3. country: Wikidata, else nearest GeoNames town to the coordinates -------------------------
d["country_iso"] = d["country_name"].str.split(" | ", regex=False).str[0].map(iso_of).fillna("")
d["country_method"] = np.where(d["country_iso"] != "", "wikidata", "")
need = kept & (d["country"] == "") & (d["loc_lat"] != "")
if need.any():
    t = np.radians(towns[["latitude", "longitude"]].astype(float).values)
    xyz = np.c_[np.cos(t[:, 0]) * np.cos(t[:, 1]), np.cos(t[:, 0]) * np.sin(t[:, 1]), np.sin(t[:, 0])]
    q = np.radians(d.loc[need, ["loc_lat", "loc_lon"]].astype(float).values)
    qx = np.c_[np.cos(q[:, 0]) * np.cos(q[:, 1]), np.cos(q[:, 0]) * np.sin(q[:, 1]), np.sin(q[:, 0])]
    i = np.array([int(np.argmax(xyz @ v)) for v in qx])  # nearest town = largest dot product
    d.loc[need, "country_iso"] = towns["countrycode"].values[i]
    d.loc[need, "country_method"] = "nearest_town"
    d.loc[need, "country_name"] = [countries.get(c, {}).get("name", c) for c in towns["countrycode"].values[i]]

# --- 4. GeoNames town named in the club's name --------------------------------------------------
idx = defaultdict(set)
for r in towns.itertuples():
    for n in {r.name, *r.alternatenames}:
        idx[(r.countrycode, norm(n))].add(r.Index)


def town_for(name, cc):
    w = re.findall(r"[\w'\-]+", norm(name))
    for size in (3, 2, 1):  # longest place name first
        hits = set()
        for i in range(len(w) - size + 1):
            g = w[i:i + size]
            if size == 1 and (g[0] in STOP or len(g[0]) < 3 or g[0].isdigit()):
                continue
            hits |= idx.get((cc, " ".join(g)), set())
        if hits:
            return hits
    return set()


todo = kept & (d["loc_lat"] == "") & (d["country_iso"] != "") & (d["name"] != "")
d["town_candidates"] = 0
d["town_candidates"] = d["town_candidates"].astype(int)
for k in d.index[todo]:
    hits = town_for(d.at[k, "name"], d.at[k, "country_iso"])
    d.at[k, "town_candidates"] = len(hits)
    if len(hits) == 1:  # only when exactly one town fits; several = for the swipe game
        r = towns.loc[next(iter(hits))]
        d.at[k, "loc_lat"], d.at[k, "loc_lon"] = str(r["latitude"]), str(r["longitude"])
        d.at[k, "loc_method"], d.at[k, "loc_precision"] = "geonames_town", "town"
        d.at[k, "loc_detail"] = r["name"]

# --- 5. recompute status for kept clubs ----------------------------------------------------------
def reasons(rules):
    out = pd.Series("", index=d.index)
    for label, mask in rules:
        out = out.where(~mask, out + ";" + label)
    return out.str.lstrip(";")


weak = d["review_reason"].str.contains("maybe_reserve_youth")
rr = reasons([
    ("no_location", d["loc_lat"] == ""),
    ("no_country", d["country_iso"] == ""),
    ("no_name", d["name"] == ""),
    ("maybe_reserve_youth", weak),
])
d.loc[kept, "review_reason"] = rr[kept]
d.loc[kept, "status"] = np.where(rr[kept] == "", "ok_for_mapping", "needs_review")

d.to_csv(OUT, index=False)
k = d[kept]
print(k["loc_method"].replace("", "none").value_counts().to_string())
print(k["status"].value_counts().to_string())
print("countries filled from coordinates:", int((k["country_method"] == "nearest_town").sum()))
print("clubs with several possible towns (swipe game):", int(((k["loc_lat"] == "") & (k["town_candidates"] > 1)).sum()))
