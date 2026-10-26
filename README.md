# football-club-geo

A worldwide list of **46,964 association football clubs** from Wikidata, built for geographic research such as mapping where clubs are, how spread out they are, and how close people live to one.

There is one row per club. Where Wikidata has a location for the club, its stadium or its town, the row also has a map point (`lat`, `lon`).

- **File:** [`data/processed/world_clubs_raw.csv`](data/processed/world_clubs_raw.csv) (UTF-8, about 12 MB)
- **Source:** Wikidata, queried with [QLever](https://qlever.cs.uni-freiburg.de/wikidata) on 2026-10-26
- **Licence:** CC0 1.0. The data comes from Wikidata, which is also CC0.

## This is raw data

Nothing has been removed. The table still includes:
- defunct clubs
- women's teams
- reserve and youth teams
- national teams
- beach soccer clubs
- duplicate items

Use the tag columns (`type_name`, `dissolved`, `parent_club_id`, `replaced_by`, `n_types`, and the rest) to filter for your own purpose.

## Coverage, so read this before you compare countries

Wikidata lists the *notable* clubs, not every registered club. For example, Germany has about 24,000 clubs registered with the DFB, but this list has 2,470 German clubs.

How complete the list is varies a lot from country to country, and so does the share of clubs that have a map point:

| Country | Clubs | With a map point |
|---|---|---|
| United Kingdom | 3,649 | 60% |
| Netherlands | 2,868 | 93% |
| Germany | 2,457 | 46% |
| France | 1,985 | 14% |
| Spain | 1,812 | 32% |
| Brazil | 1,744 | 40% |

Overall, 17,105 clubs (36%) have a map point. If you compare countries without accounting for this, you will partly be comparing how well each country is covered in Wikidata.

## Columns

Where a club has several values for one field (for example two stadiums), they are joined with ` | `. In the paired columns (`*_id`, name, `*_coord`), the values appear in the same order.

| Column | Meaning |
|---|---|
| `club` | Wikidata ID, e.g. `Q15789` |
| `name_en` | English label |
| `name_de` … `name_pt`, `name_mul` | Labels in German, Spanish, French, Italian, Dutch, Portuguese, and the language-neutral `mul` label |
| `country_name`, `country` | Country (P17), name and ID |
| `lat`, `lon` | One best map point (WGS84) |
| `location_source` | Where `lat`/`lon` came from: `club` (the club's own coordinate, P625), else `venue` (its home ground, P115), else `place` (the town it's in, P131), else blank |
| `type_name`, `type` | What the item is an instance of (P31), e.g. *association football club*, *defunct association football club*, *women's association football club* |
| `founded`, `dissolved` | Dates founded (P571) and dissolved (P576) |
| `club_coord` | The club's own coordinate, as `POINT(lon lat)` |
| `place_id`, `place_name`, `place_coord` | Located in (P131) |
| `venue_id`, `venue_name`, `venue_coord` | Home venue (P115) |
| `league_id`, `league` | League (P118) |
| `competition_class_id`, `competition_class` | Competition class (P2094), e.g. women's or under-19 |
| `sport_id`, `sport` | Sport (P641) |
| `parent_club_id` | Parent club (P831). This is filled in for reserve and B teams |
| `replaced_by_id`, `replaced_by` | Replaced by (P1366), e.g. after a merger |
| `part_of_id`, `part_of` | Part of (P361). This is often a district association rather than a parent club |
| `owned_by_id`, `owned_by` | Owned by (P127) |
| `transfermarkt_id` | Transfermarkt team ID (P7223) |
| `n_countries`, `n_types` | Number of countries and types listed. A value above 1 is worth checking |
| `wikidata_url` | Link to the item |

## Known gaps

- 3,805 clubs have no country.
- 3,394 clubs have no name in any of the languages above. These are mostly clubs whose names exist only in other scripts, such as Cyrillic or Arabic.
- The coordinate for a `place` is the centre of the town or district, not the ground itself.

## How it was built

1. The queries in [`queries/world/`](queries/world) find every item that is an instance of *association football club* or any subtype of it (`wdt:P31/wdt:P279* wd:Q476028`). The work is split into eight queries so that none of them times out.
2. The exports of those queries are in [`data/incoming/world/`](data/incoming/world), unchanged.
3. [`scripts/merge_world.py`](scripts/merge_world.py) merges them into one row per club. To rebuild the table, run `python scripts/merge_world.py`, which needs pandas.

Check: the German subset of this table matches a separate Wikidata Query Service export exactly (2,470 clubs), which shows that none of the downloads were cut short.
