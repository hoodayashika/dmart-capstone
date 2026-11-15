# Data quality report: data/store_daily.csv (raw file)

All figures below are computed on the **raw** file by `scripts/clean_data.py`.

## Shape

453 rows by 9 columns.

## Data type and null count of every column

| column | dtype (pandas 3.0.6) | nulls |
|---|---|---|
| date | str | 0 |
| store_id | str | 0 |
| store | str | 0 |
| footfall | float64 | 4 |
| revenue_inr | float64 | 0 |
| daily_target_inr | int64 | 0 |
| marketing_spend_inr | int64 | 0 |
| stockout_hours | float64 | 0 |
| discount_pct | float64 | 0 |

Exact duplicate rows: **3** (every column identical to an earlier row).

Footfall minimum: **-150**; maximum: **9800**; missing footfall values: **4**.

## Footfall bounds per store (IQR method)

Computed after removing the exact duplicates and after treating negative footfall as missing, using non-missing values only. Percentiles use linear interpolation, as `df.describe()` does.

| store | Q1 | Q3 | IQR | lower bound (Q1 - 1.5*IQR) | upper bound (Q3 + 1.5*IQR) |
|---|---|---|---|---|---|
| Ahmedabad | 1844.500 | 2019.250 | 174.750 | 1582.375 | 2281.375 |
| Bengaluru | 1952.000 | 2211.000 | 259.000 | 1563.500 | 2599.500 |
| Hyderabad | 2053.000 | 2356.000 | 303.000 | 1598.500 | 2810.500 |
| Mumbai | 2246.000 | 2542.000 | 296.000 | 1802.000 | 2986.000 |
| Pune | 1434.000 | 1593.500 | 159.500 | 1194.750 | 1832.750 |

Rows outside their store's bounds: **2**.

| store | date | footfall | lower bound | upper bound |
|---|---|---|---|---|
| Ahmedabad | 2026-05-26 | 9800 | 1582.375 | 2281.375 |
| Mumbai | 2026-04-09 | 6100 | 1802.000 | 2986.000 |

## Decisions

Treatments were applied in this order: duplicates, negatives, extremes, missing values.

### 1. Exact duplicate rows

- **What I did:** removed the 3 exact duplicates (Mumbai 2026-05-11, Hyderabad 2026-05-31, Ahmedabad 2026-04-16), keeping the first occurrence of each. 453 rows became 450 (5 stores x 90 days).
- **Why:** a store has one row per day, so a second identical row would double count that day's revenue and footfall in every average. Keeping the first occurrence is safe because the copies are identical in every column.
- **Raw file still contains:** all 3 duplicate rows, at the end of `data/store_daily.csv`. The raw file is never edited.

### 2. Negative values

- **What I did:** set the one negative footfall (Hyderabad 2026-04-21, -150) to missing, so it is then filled by the median step.
- **Why not zero:** a store that sold goods that day cannot have had zero visitors, and a zero would drag the store's average and the revenue-per-footfall ratio. **Why not delete the row:** the row's revenue, target and stockout hours are valid and are needed for revenue and target questions.
- **Raw file still contains:** the value -150.

### 3. Extreme values

- **What I did:** capped the 2 extreme footfall values at the nearest bound of their own store: Ahmedabad 2026-05-26 (9800 became 2281.38) and Mumbai 2026-04-09 (6100 became 2986.00).
- **Why cap, not delete:** those days have real revenue (a busy day is genuine, only the footfall figure is implausible), so deleting the row would lose revenue. Capping keeps the row and stops one value from distorting the mean and the correlation. **Why per-store bounds:** stores differ in size, so one pooled bound would be wrong for both Pune and Mumbai.
- **Raw file still contains:** 9800 and 6100.

### 4. Missing values

- **What I did:** filled each remaining missing footfall (the 4 blanks plus the 1 value made missing in step 2, so 5 in all) with the median of that store's non-missing footfall (after capping).
- **Why the median, not the mean:** the median is not pulled by extreme days. **Why per store, not the all-store median:** store sizes differ (Pune about 1500, Mumbai about 2400). **Why not zero:** zero would be an invented, impossible value.
- **Raw file still contains:** the 4 blank footfall cells (Mumbai 2026-04-30, Pune 2026-04-12, Pune 2026-05-17, Bengaluru 2026-06-10).

`revenue_inr` and every other column were left untouched.
