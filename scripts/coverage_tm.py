"""League-size coverage from Transfermarkt (2025/26 season, 29 countries).

For each country: how many club places there are across all its leagues on Transfermarkt (league size total),
how many of those clubs are in our Wikidata list (matched by Transfermarkt ID), and how many of those have a map point.
Output: data/coverage/coverage_transfermarkt_2025.csv (per country) and coverage_transfermarkt_leagues_2025.csv (per league)
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "coverage"

seasons = pd.read_csv(RAW / "team_competitions_seasons.csv", dtype=str, low_memory=False)
details = pd.read_csv(RAW / "team_details.csv", dtype=str)
clubs = pd.read_csv(ROOT / "data" / "processed" / "world_clubs_raw.csv", dtype=str, keep_default_na=False)

s = seasons[seasons.season_id == "2025"].copy()
s["tm_country"] = s.club_id.map(details.drop_duplicates("club_id").set_index("club_id").country_name)
s["level"] = pd.to_numeric(s.season_league_level_level_number)

# Our list: one row per Transfermarkt ID (some clubs list several IDs)
tm = clubs.assign(tm=clubs.transfermarkt_id.str.split(" | ", regex=False)).explode("tm")
tm = tm[tm.tm != ""].drop_duplicates("tm").set_index("tm")
s["in_list"] = s.club_id.isin(tm.index)
s["on_map"] = s.club_id.map(tm.lat).fillna("") != ""

leagues = (s.groupby(["tm_country", "level", "competition_name"])
           .agg(league_size=("club_id", "nunique"), in_list=("in_list", "sum"), on_map=("on_map", "sum"))
           .reset_index().sort_values(["tm_country", "level", "competition_name"]))
leagues.to_csv(OUT / "coverage_transfermarkt_leagues_2025.csv", index=False)

country = (s.drop_duplicates(["tm_country", "club_id"]).groupby("tm_country")
           .agg(league_clubs=("club_id", "nunique"), in_list=("in_list", "sum"), on_map=("on_map", "sum"),
                tiers=("level", "max"))
           .reset_index())
top = s[s.level == 1].drop_duplicates(["tm_country", "club_id"]).groupby("tm_country") \
       .agg(top_size=("club_id", "nunique"), top_in_list=("in_list", "sum"), top_on_map=("on_map", "sum"))
country = country.join(top, on="tm_country")
country["pct_in_list"] = (100 * country.in_list / country.league_clubs).round(0)
country["pct_on_map"] = (100 * country.on_map / country.league_clubs).round(0)
country.sort_values("pct_in_list").to_csv(OUT / "coverage_transfermarkt_2025.csv", index=False)
print(country.sort_values("pct_in_list").to_string(index=False))
