# Findings: Pune and the stockout premise

Source: `data/store_daily_clean.csv` (450 rows = 5 stores x 90 days, 2026-04-01 to 2026-06-29). Synthetic practice data.

## Store table

| store | mean daily revenue (INR) | mean footfall | mean stockout hours | revenue per footfall (INR) | mean achievement_pct | days in Poor band |
|---|---|---|---|---|---|---|
| Ahmedabad | 782647.37 | 1922.59 | 3.19 | 407.08 | 92.08 | 1 |
| Bengaluru | 931065.68 | 2076.86 | 2.38 | 448.31 | 98.01 | 0 |
| Hyderabad | 893233.01 | 2209.51 | 3.85 | 404.27 | 94.02 | 0 |
| Mumbai | 1064371.60 | 2391.27 | 1.93 | 445.11 | 101.37 | 0 |
| Pune | 636358.55 | 1517.71 | 2.32 | 419.29 | 70.71 | 70 |
| All stores | 861535.24 | 2023.59 | 2.74 | 425.75 | 91.24 | 71 |

Revenue per footfall is each store's total revenue divided by its total footfall.

## Premise test

Premise: *Pune is the lowest-revenue store because of stockouts.* If it were true, Pune should have the most stockout hours.

Ranking of the five stores by mean stockout hours (highest first):

1. Hyderabad: 3.85 hours
2. Ahmedabad: 3.19 hours
3. Bengaluru: 2.38 hours
4. Pune: 2.32 hours
5. Mumbai: 1.93 hours

**Answer: no.** Pune ranks 4th of 5 by mean stockout hours (2.32 against an all-store mean of 2.74). Hyderabad is highest (3.85). The premise "Pune has the most stockouts" is **not supported** by the data.

### Correlations (Pearson)

| pair | rows | r |
|---|---|---|
| revenue_inr vs stockout_hours | all 450 | -0.152 |
| revenue_inr vs footfall | all 450 | 0.918 |
| revenue_inr vs stockout_hours | Pune 90 | -0.254 |
| revenue_inr vs footfall | Pune 90 | 0.735 |
| revenue_inr vs footfall, **before cleaning** (deduplicated raw rows with non-missing footfall, negative and extreme values still in) | 446 | 0.548 |

Cleaning changed the revenue-footfall correlation from 0.548 to 0.918: the impossible -150 and the two extreme values (6100, 9800) were hiding the real relationship.

Correlation does not establish causation: these figures show how the variables move together, not that one produces the other.

## Facts, Insights, Hypotheses

### Facts (numbers straight from the data)

- Pune's mean daily revenue is INR 636358.55, the lowest of the five stores; the all-store mean is INR 861535.24.
- Pune's mean footfall is 1517.71 against 2023.59 for all stores.
- Pune's mean stockout hours are 2.32, ranked 4th of 5; Hyderabad has 3.85.
- Pune's revenue per footfall is INR 419.29 against INR 425.75 for all stores.
- Pune had 70 of 71 Poor-band days in the whole data set.
- Pune's daily target is INR 900000 and Mumbai's is INR 1050000.

### Insights (interpretations)

1. Pune's revenue is 26.14% below the all-store mean and its footfall is 25.00% below; revenue per footfall is only 1.52% below. Almost the whole revenue gap is therefore a footfall gap, not a stockout (or basket) gap.
2. Revenue is somewhat lower on high-stockout days (r = -0.254 in Pune) but footfall moves with revenue far more strongly (r = 0.735 in Pune, 0.918 across all rows); a stockout programme would address the weaker of the two relationships, and Pune does not even have the most stockouts.
3. Pune's target (INR 900000) is only 14.3% below Mumbai's, while Pune's revenue is 40.2% below Mumbai's, so the target is not scaled to Pune's footfall, which is why Pune sits in the Poor band on 70 days.

### Hypotheses (unconfirmed)

1. **Unconfirmed:** Pune's low footfall comes from a smaller or more competitive catchment area. *Data needed:* catchment population, competitor store locations and store floor area per city.
2. **Unconfirmed:** pricing perception keeps shoppers away (the most frequent Pune feedback theme is Pricing). *Data needed:* price comparison against nearby competitors and the share of feedback by theme over time, with more than 40 comments.
3. **Unconfirmed:** lower local marketing contributes to lower footfall (Pune spends INR 41643 a day on average against INR 53731 in Mumbai). *Data needed:* campaign-level spend and a before/after test of footfall.
