# UAE Automobile Demand Intelligence Platform
## Data Dictionary — UAE Edition (automobile_datasets / "test" mode)

This is the larger of the two generated UAE datasets, used when the app is in "test" data
mode (`database.connection.set_data_mode("test")`). It shares the exact same schema and
7-emirate / 15-brand market model as `realdata-datasets/` (see
`realdata-datasets/DATA_DICTIONARY.md` for the full field-by-field description and the
real-world macro anchors baked into `external_factors.csv`) — this file only notes what's
different about the "test" dataset.

Both dataset folders are produced by the same generator, `preprocessing/generate_uae_data.py`,
run with different parameters. The "test" set uses a legacy even-grid market layout
(15 independent dealers per emirate) rather than the single 24-rooftop dealer group the
"real" set models.

## Differences from realdata-datasets

| | automobile_datasets (test) | realdata-datasets (real) |
|---|---|---|
| customers.csv | 98,000 rows | 70,000 rows |
| dealers.csv | 105 rows (15 per emirate, even grid) | 24 rows (one dealer group) |
| vehicles.csv | ~309 rows (3 trims per model) | ~206 rows (2 trims per model) |
| sales.csv | 140,000 rows | 100,000 rows |
| inventory.csv | ~87,000 rows | ~13,000 rows |
| external_factors.csv | 644 rows (7 emirates × 92 months) | 644 rows (7 emirates × 92 months) |
| generator seed | 7 | 42 |

Vehicle `variant` values are real per-brand trim names (Toyota GX/GXR/VXR,
Nissan S/SE/SL, Mitsubishi GLX/GLS/Highline, …). This dataset carries the first
three rungs of each ladder; `realdata-datasets/` carries the first two. Trim
pricing steps +10% and +22% over the base trim.

## Regeneration

Run `python -m preprocessing.generate_uae_data` to regenerate both dataset folders, then
`python -m preprocessing.seed_database` to reseed `automobile_demand.db`.
