# football-club-geo

A worldwide list of **46,964 association football clubs** from Wikidata, built for geographic research such as mapping where clubs are, how spread out they are, and how close people live to one.

There is one row per club. Where Wikidata has a location for the club, its stadium or its town, the row also has a map point (`lat`, `lon`).

- **File:** [`data/processed/world_clubs_raw.csv`](data/processed/world_clubs_raw.csv) (UTF-8, about 12 MB)
- **Source:** Wikidata, queried with [QLever](https://qlever.cs.uni-freiburg.de/wikidata) on 2026-10-26
- **Licence:** CC0 1.0. The data comes from Wikidata, which is also CC0. The cleaned and located table adds some columns under other open licences; see [Licences and credits](#licences-and-credits).

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

## Cleaned and located table

[`data/processed/world_clubs_located.csv`](data/processed/world_clubs_located.csv) is the same 46,964 clubs, with flags and a best location for each club. Nothing is deleted: clubs that are left out of the study are marked `excluded`, with the reason.

**Status** (`status`, `exclude_reason`, `review_reason`):

| Status | Clubs | Meaning |
|---|---|---|
| `excluded` | 5,656 | Defunct (has a dissolved date or a "defunct" type), national teams, reserve or youth sides (has a parent club, or the name ends in B/II/III or contains U21, Reserves and so on), and beach soccer clubs. Women's clubs are kept. |
| `ok_for_mapping` | 25,229 | Has a name, a country and a location |
| `needs_review` | 16,079 | Something is missing or unclear. `review_reason` says what: `no_location`, `no_country`, `no_name` or `maybe_reserve_youth` (names with words like Academy or Youth, which real clubs also use) |

**Location** (`loc_lat`, `loc_lon`, `loc_method`, `loc_precision`, `loc_detail`). Every location is tagged with how it was found:

| `loc_method` | Kept clubs | Precision | Where the point comes from |
|---|---|---|---|
| `wikidata_club` | 2,909 | ground | The club's own coordinate on Wikidata |
| `wikidata_venue` | 8,612 | ground | Its home ground's coordinate on Wikidata |
| `wikidata_place` | 3,455 | town | The town or area Wikidata says it is in |
| `overture_exact` | 3,339 | ground | A place in [Overture Maps](https://overturemaps.org) whose name exactly matches the club's in the same country, after removing words like FC or Club. `loc_detail` names the place |
| `geonames_town` | 7,412 | town | A town named in the club's name (for example "FC Schepdaal" → Schepdaal), found in [GeoNames](https://www.geonames.org) in the club's country. Used only when exactly one town fits |
| blank | 15,581 | | No location found yet |

Checks against clubs whose ground was already on Wikidata: Overture exact matches were within 5 km of it 83% of the time, and the GeoNames town was within 10 km 86% of the time.

`country_iso` and `country_method` give the club's country: `wikidata`, or `nearest_town` for 214 clubs where Wikidata had no country, filled from the nearest GeoNames town to the club's location.

[`data/processed/overture_matches.csv`](data/processed/overture_matches.csv) lists every Overture match, including the uncertain ones (`match_type` = `iffy`, 2,113 clubs with no location), with the top candidates for a person to check.

### How it was built

1. [`scripts/flag_clubs.py`](scripts/flag_clubs.py) adds the flags, giving `world_clubs_flagged.csv`.
2. [`scripts/fetch_overture_football.py`](scripts/fetch_overture_football.py) reads the Overture Maps places release (2026-10-21.0) from its public S3 bucket and keeps about 2.8 million places that may be football-related. The download isn't stored here because it's too large; run the script to rebuild it (needs pyarrow).
3. [`scripts/match_overture.py`](scripts/match_overture.py) matches clubs to those places by name and country (needs rapidfuzz and geonamescache).
4. [`scripts/locate_clubs.py`](scripts/locate_clubs.py) picks each club's location in the order of the table above and recomputes the status.

## Licences and credits

- Data from Wikidata (everything in `world_clubs_raw.csv`) is CC0 1.0.
- Columns that come from Overture Maps (the `overture_exact` locations, `loc_detail` for those rows, and the `ov_*` columns in `overture_matches.csv`) are under the [CDLA-Permissive-2.0](https://cdla.dev/permissive-2-0/) licence. © Overture Maps Foundation.
- Locations and countries that come from GeoNames (`geonames_town`, `nearest_town`) are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Data from GeoNames (geonames.org), used through the geonamescache package.

So the CC0 licence in [`LICENSE`](LICENSE) covers the Wikidata data only. Please give the credits above if you reuse the Overture or GeoNames columns.

## Work in progress: how complete is the list?

We're checking how many clubs a country *should* have against how many are in this list.

- [`data/coverage/`](data/coverage) compares each country's 2025/26 league clubs on Transfermarkt with this list, for 29 countries. Clubs are matched by Transfermarkt ID, so the "in list" figures are a minimum. The script is [`scripts/coverage_tm.py`](scripts/coverage_tm.py). It needs the Transfermarkt open data from [salimt/football-datasets](https://github.com/salimt/football-datasets) in `data/raw/`.
- [`scripts/fetch_api_football.py`](scripts/fetch_api_football.py) downloads every men's league and its teams from [API-Football](https://www.api-football.com). On the free plan this covers the 2024 season at about 95 requests a day. You need your own key, and the raw downloads aren't shared here.
- [`queries/world/5_league_sizes.rq`](queries/world/5_league_sizes.rq) lists every football league in Wikidata with its number of teams. It hasn't been tested yet.
