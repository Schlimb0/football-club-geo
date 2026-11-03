"""Add cleaning flags to the world club table (flag, never delete).

Rules agreed by Liam on 2026-11-01:
  exclude  defunct        - has a dissolved date, or its Wikidata type says "defunct"
  exclude  national_team  - its Wikidata type is a national team
  exclude  reserve_youth  - it is linked to a parent club on Wikidata (P831)
  women's clubs are KEPT.
Added by Liam on 2026-11-01 (second round):
  exclude  beach_soccer   - its Wikidata type is a beach soccer club
  exclude  reserve_youth  - its name clearly marks a second/youth side: ends in II, III, IV, B or C,
                            or contains U21 / Under-21 / Sub-20 / Reserves
  Weaker name words (Academy, Youth, Juniors, Primavera, Jugend, Juvenil) are NOT excluded:
  they also appear in real club names, so they get review_reason "maybe_reserve_youth".

Everything not excluded is then sorted:
  ok_for_mapping  - has a name, a country and coordinates
  needs_review    - anything missing; review_reason lists what (no_location, no_country, no_name)

Input:  data/processed/world_clubs_raw.csv
Output: data/processed/world_clubs_flagged.csv  (all raw columns + name, status, exclude_reason, review_reason)
Run from the project root:  python scripts/flag_clubs.py
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "processed" / "world_clubs_raw.csv"
OUT = ROOT / "data" / "processed" / "world_clubs_flagged.csv"
NAME_COLS = ["name_en", "name_mul", "name_de", "name_fr", "name_es", "name_it", "name_nl", "name_pt"]

d = pd.read_csv(IN, dtype=str, keep_default_na=False)
t = d["type_name"].str.lower()

# best available name: English first, then other languages
name = d[NAME_COLS[0]]
for c in NAME_COLS[1:]:
    name = name.where(name != "", d[c])
d.insert(1, "name", name)


def reasons(rules):
    out = pd.Series("", index=d.index)
    for label, mask in rules:
        out = out.where(~mask, out + ";" + label)
    return out.str.lstrip(";")


STRONG = (d["name"].str.contains(r"\s(?:II|III|IV|B|C)$", regex=True)
          | d["name"].str.contains(r"\b(?:U-?\d{2}s?|Under[- ]?\d{2}s?|Sub-?\d{2}|Reserves?)\b", case=False, regex=True))
WEAK = d["name"].str.contains(r"\b(?:Academy|Youth|Juniors?|Primavera|Jugend|Juvenil)\b", case=False, regex=True)

d["exclude_reason"] = reasons([
    ("defunct", (d["dissolved"] != "") | t.str.contains("defunct")),
    ("national_team", t.str.contains("national")),
    ("reserve_youth", (d["parent_club_id"] != "") | STRONG),
    ("beach_soccer", t.str.contains("beach soccer")),
])
d["review_reason"] = reasons([
    ("no_location", d["lat"] == ""),
    ("no_country", d["country"] == ""),
    ("no_name", d["name"] == ""),
    ("maybe_reserve_youth", WEAK),
])
d.loc[d["exclude_reason"] != "", "review_reason"] = ""

d.insert(2, "status", "needs_review")
d.loc[d["review_reason"] == "", "status"] = "ok_for_mapping"
d.loc[d["exclude_reason"] != "", "status"] = "excluded"

d.to_csv(OUT, index=False)
print(d["status"].value_counts().to_string())
