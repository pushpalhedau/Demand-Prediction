# North America Automobile Demand Intelligence Platform
## Data Dictionary — NA Edition (automobile_datasets / "test" mode)

This is the larger of the two generated NA datasets, used when the app is in "test" data
mode (`database.connection.set_data_mode("test")`). It shares the exact same schema and
8-state / 16-brand market model as `realdata-datasets/` (see
`realdata-datasets/DATA_DICTIONARY.md` for the full field-by-field description and the
real-world macro anchors baked into `external_factors.csv`) — this file only notes what's
different about the "test" dataset.

Both dataset folders are produced by the same generator, `preprocessing/generate_na_data.py`,
run with different parameters.

## Differences from realdata-datasets

| | automobile_datasets (test) | realdata-datasets (real) |
|---|---|---|
| customers.csv | 56,000 rows | 42,000 rows |
| dealers.csv | 120 rows (15 per state) | 48 rows (6 per state) |
| vehicles.csv | 273 rows (3 trims per model) | 182 rows (2 trims per model) |
| sales.csv | 140,000 rows | 100,000 rows |
| inventory.csv | 90,072 rows (120 dealers x 36 month-ends) | 24,120 rows (48 dealers x 36 month-ends) |
| external_factors.csv | 736 rows (8 states × 92 months) | 736 rows (8 states × 92 months) |
| generator seed | 7 | 42 |

Vehicle `variant` values are real per-brand trim names taken from the brand's actual trim
ladder (Toyota LE/XLE/Limited, Ford XL/XLT/Lariat, Honda LX/Sport/EX-L, and so on). This
dataset carries the first three rungs of each ladder; `realdata-datasets/` carries the
first two. Trim pricing steps +9% and +19% over the base trim.

## Regeneration

Run `python -m preprocessing.generate_na_data` to regenerate both dataset folders, then
`python -m preprocessing.seed_database` to reseed `automobile_demand.db`.
