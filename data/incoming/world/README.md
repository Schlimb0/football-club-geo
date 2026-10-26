# World Wikidata exports (QLever, run by Liam on 2026-10-26)

Raw exports, untouched apart from renaming. Each file came from the query of the same number in `queries/world/`.
All files join on the `club` column (the Wikidata item URL). Merged into one row per club by `scripts/merge_world.py`,
giving `data/processed/world_clubs_raw.csv`.

| File | Query | Rows | Clubs |
|---|---|---|---|
| world_1_core.csv | 1_core.rq | 47,888 | 46,964 |
| world_2_names.csv | 2_names.rq | 102,168 | 35,032 |
| world_3a_club_coords.csv | 3a_club_coords.rq | 3,019 | 3,015 |
| world_3b_places.csv | 3b_places.rq | 5,044 | 4,849 |
| world_3c_venues.csv | 3c_venues.rq | 11,742 | 11,381 |
| world_4a1_league_class_sport.csv | 4a1_league_class_sport.rq | 66,993 | 45,379 |
| world_4a2_merged_partof_owner.csv | 4a2_merged_partof_owner.rq | 2,360 | 2,219 |
| world_4b_links.csv | 4b_links.rq (two-column version) | 7,201 | 7,103 |

`superseded/world_4b_links_longformat.csv` holds the same parent club and Transfermarkt data in the older long format. It's kept only for the record.

**Completeness check:** the German subset matches the earlier Wikidata Germany export exactly: 2,470 clubs, 28 own coordinates, 1,018 places, 283 venues, 416 parent clubs, 154 Transfermarkt IDs. So the downloads weren't cut short.
