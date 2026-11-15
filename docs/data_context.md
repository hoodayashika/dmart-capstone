# Data context

All three datasets are synthetic, written by `scripts/generate_data.py` (seed 2604). The raw files are never edited.
The datasets are related by the **store name** (the `store` column, with `store_id` S01 to S05 alongside it).

## store_daily (`data/store_daily_clean.csv`, cleaned in Part A)

- **Rows:** 450 (5 stores x 90 days). The raw file `data/store_daily.csv` has 453 rows and 9 columns.
- **Date range:** 2026-04-01 to 2026-06-29.
- **Columns and types:** `date` (text, ISO), `store_id` (text), `store` (text), `footfall` (decimal), `revenue_inr` (decimal),
  `daily_target_inr` (integer), `marketing_spend_inr` (integer), `stockout_hours` (decimal), `discount_pct` (decimal), and six feature
  columns: `revenue_per_footfall`, `marketing_efficiency`, `achievement_pct`, `shortfall_inr` (decimals), `weekend_flag` (Yes/No text),
  `performance_band` (Excellent / Good / Poor text).
- **Data-quality facts from Part A:** 3 exact duplicate rows were removed; 1 negative footfall (Hyderabad 2026-04-21, -150) was set to
  missing; 2 extreme footfall values were capped at their store's IQR bound (Ahmedabad 9800 to 2281.38, Mumbai 6100 to 2986.00);
  4 blank footfall values plus the negative one, 5 in all, were filled with that store's median footfall. `revenue_inr` and all other columns
  were not changed.
- **What the cleaned file guarantees:** exactly 450 rows, no missing value in any column, no negative footfall, one row per store per day.
- **Supports:** revenue, target, footfall, stockout and discount lookups for a store and date or range; target versus actual
  (`achievement_pct`, `performance_band`); cross-store comparisons. **Does not support:** the unapproved columns, or any date outside the range.

## inventory (`data/inventory.csv`)

- **Rows:** 40 (5 stores x 8 products). **Date range:** none. This dataset has no date column, so it is a single snapshot.
- **Columns and types:** `store_id` (text), `store` (text), `product_id` (text), `product` (text, name with size such as Amul Milk 1L),
  `stock_units` (integer), `reorder_threshold` (integer).
- **Data-quality facts:** no missing values. A store is short of a product when `stock_units` is strictly below `reorder_threshold`
  (for Amul Milk: Hyderabad 40 and Pune 85 against 100; Ahmedabad is exactly 100, so it is not short).
- **Supports:** which stores are below the reorder threshold for a product, or the stock position of one product in one store.
  **Does not support:** stock over time, or any question with a date.

## feedback (`data/feedback.csv`)

- **Rows:** 200 (40 per store). **Date range:** 2026-04-01 to 2026-06-29 (the date is carried but feedback answers cover all of a store's rows).
- **Columns and types:** `feedback_id` (text), `store_id` (text), `store` (text), `date` (text, ISO), `rating` (integer 1 to 5, blank when unrated),
  `theme` (text: Stock availability, Queue time, Pricing, Freshness, Staff behaviour).
- **Data-quality facts:** 12 rows have no rating. They stay unrated: an average is taken over the 188 rated rows only and is reported
  with the count of rated rows and of all rows. A missing rating is never replaced by an average.
- **Supports:** a store's average rating, the rated and total counts, and its most frequent theme. **Does not support:** causes, trends over time,
  or free-text comments (there are none).

## Weather (tool, not a dataset)

`tools/weather.py` returns temperature, humidity, wind and rain for one store city and one date. In the default stub mode the values come
from a fixed formula, so they are illustrative and not real weather.
