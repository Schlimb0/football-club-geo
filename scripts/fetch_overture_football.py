"""Pull football-related places from Overture Maps Places (open data, CDLA-Permissive-2.0).

Reads the public Overture release straight from S3 (anonymous), keeps only places that look
football-related, and writes them to data/incoming/overture/overture_football_places.csv.

A place is kept if ANY of these is true:
  - its category is a sports team / club / stadium / field (see KEEP_CATS), or mentions soccer/football
  - its name contains a football word (FC, football, soccer, futbol, calcio, fussball, voetbal ...)
  - it has a Wikidata id (brand.wikidata) - used for exact matches to our clubs

Run from the project root:  python scripts/fetch_overture_football.py [release]
Needs: pip install pyarrow
"""
import re
import sys
import csv
from pathlib import Path
import pyarrow.fs as fs
import pyarrow.parquet as pq

RELEASE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-21.0"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "incoming" / "overture" / "overture_football_places.csv"
BUCKET = "overturemaps-us-west-2"
PREFIX = f"{BUCKET}/release/{RELEASE}/theme=places/type=place/"

KEEP_CATS = {"sport_team", "professional_sport_team", "amateur_sport_team", "school_sport_team",
             "sport_or_recreation_club", "stadium_arena", "sport_field", "sports_club_and_league",
             "sport_league", "amateur_sport_league", "professional_sport_league", "sports_and_recreation"}
NAME_RE = re.compile(
    r"\b(f\.?\s?c|a\.?f\.?c|s\.?c|football|soccer|f[uú]tbol|futebol|calcio|fu(ss|ß)ball|voetbal|"
    r"fotball|fotboll|fodbold|jalkapallo|futbal|fudbal|nogomet|labdar[uú]g|pi[lł]ka|futbol|"
    r"sportverein|sv|tsv|vfb|vfl|fk|nk|sk|ks|tj|cd|ud|ss|asd|usd|stade|estadio|stadion|stadium)\b",
    re.I)
COLS = ["id", "names", "basic_category", "taxonomy", "addresses", "bbox", "confidence", "brand", "websites"]

s3 = fs.S3FileSystem(anonymous=True, region="us-west-2")
files = sorted(i.path for i in s3.get_file_info(fs.FileSelector(PREFIX)) if i.path.endswith(".parquet"))
OUT.parent.mkdir(parents=True, exist_ok=True)
kept = 0
with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["overture_id", "name", "basic_category", "category", "country", "locality",
                "lat", "lon", "confidence", "wikidata", "website"])
    for n, path in enumerate(files, 1):
        pf = pq.ParquetFile(s3.open_input_file(path))
        for rg in range(pf.metadata.num_row_groups):
            for r in pf.read_row_group(rg, columns=COLS).to_pylist():
                name = (r["names"] or {}).get("primary") or ""
                bc = r["basic_category"] or ""
                cat = (r["taxonomy"] or {}).get("primary") or ""
                wd = (r["brand"] or {}).get("wikidata") or ""
                if not (bc in KEEP_CATS or "soccer" in cat or "football" in cat or wd
                        or NAME_RE.search(name)):
                    continue
                a = (r["addresses"] or [{}])[0] or {}
                b = r["bbox"] or {}
                w.writerow([r["id"], name, bc, cat, a.get("country") or "", a.get("locality") or "",
                            round(((b.get("ymin") or 0) + (b.get("ymax") or 0)) / 2, 6),
                            round(((b.get("xmin") or 0) + (b.get("xmax") or 0)) / 2, 6),
                            r["confidence"], wd, (r["websites"] or [""])[0]])
                kept += 1
        print(f"file {n}/{len(files)} done, {kept:,} places kept so far", flush=True)
print("done", kept)
