# Golden set derivation

Expected values of my own cases (and R01) were calculated from `data/store_daily_clean.csv`, `data/inventory.csv` and
`data/feedback.csv` with the pandas expressions below, **not** copied from the agent's output. `c` is the cleaned store_daily
DataFrame, `inv` is inventory.csv, `fb` is feedback.csv. Values are written with 2 decimals (pandas rounding is half-even on the
binary value, the agent rounds half-up; `run_eval.py` accepts a difference up to 0.01).

| case | what | pandas expression / hand calculation | value |
|---|---|---|---|
| O10a/O11a/O12a/O13a (setup lookups) | Pune revenue on 2026-05-15 | `c[(c.store=='Pune')&(c.date=='2026-05-15')].revenue_inr.iloc[0]` | 623845.00 |
| O01 | Bengaluru revenue on 2026-06-15 | `c[(c.store=='Bengaluru')&(c.date=='2026-06-15')].revenue_inr.iloc[0]` | 1018621.30 |
| O02 | Bengaluru revenue on 2026-05-15 | `c[(c.store=='Bengaluru')&(c.date=='2026-05-15')].revenue_inr.iloc[0]` | 970774.76 |
| O14 | Pune mean rating over rated rows | `fb[fb.store=='Pune'].rating.mean()  (NaN skipped)` | 3.71 |
| O14 | Pune rated rows | `fb[fb.store=='Pune'].rating.notna().sum()` | 38 |
| O14 | Pune all feedback rows | `len(fb[fb.store=='Pune'])` | 40 |
| O14 | Pune most frequent theme | `fb[fb.store=='Pune'].theme.value_counts().idxmax()  (counts: {'Pricing': 20, 'Stock availability': 7, 'Freshness': 6, 'Queue time': 5, 'Staff behaviour': 2})` | Pricing |
| O15 | Mumbai mean footfall 2026-04-01..2026-04-30 | `c[(c.date>='2026-04-01')&(c.date<='2026-04-30')].groupby('store').footfall.mean().round(2)` | 2442.93 |
| O15 | Hyderabad mean footfall 2026-04-01..2026-04-30 | `c[(c.date>='2026-04-01')&(c.date<='2026-04-30')].groupby('store').footfall.mean().round(2)` | 2156.30 |
| O15 | Bengaluru mean footfall 2026-04-01..2026-04-30 | `c[(c.date>='2026-04-01')&(c.date<='2026-04-30')].groupby('store').footfall.mean().round(2)` | 2092.47 |
| O15 | Ahmedabad mean footfall 2026-04-01..2026-04-30 | `c[(c.date>='2026-04-01')&(c.date<='2026-04-30')].groupby('store').footfall.mean().round(2)` | 1901.33 |
| O15 | Pune mean footfall 2026-04-01..2026-04-30 | `c[(c.date>='2026-04-01')&(c.date<='2026-04-30')].groupby('store').footfall.mean().round(2)` | 1513.65 |
| O16 | stores below threshold for Iodised Salt 1kg | `inv[(inv['product']=='Iodised Salt 1kg')&(inv.stock_units<inv.reorder_threshold)]` | 0 rows (empty) |
| O17 | Mumbai revenue 2026-05-21 | `c[(c.store=='Mumbai')&(c.date=='2026-05-21')].revenue_inr.iloc[0]` | 1133910.49 |
| O17 | Mumbai achievement_pct 2026-05-21 | `revenue_inr / daily_target_inr * 100 = 1133910.49 / 1050000 * 100` | 107.99 |
| O17 | stub weather Mumbai 2026-05-21 (hand calc from the stub formula) | `doy=141, n=6: temp=20+(6+141)%15, humidity=40+(18+141)%50, wind=5+141%10, rain=6.5 if 141%4==0 else 0.0` | 32.0, 49.0, 6.0, 0.0 mm |
| O18 | Ahmedabad mean footfall 2026-05-01..2026-05-31 | `c[(c.store=='Ahmedabad')&(c.date>='2026-05-01')&(c.date<='2026-05-31')].footfall.mean()` | 1947.01 |
| O19 | Mumbai mean stockout_hours 2026-05-01..2026-05-31 | `c[(c.date>='2026-05-01')&(c.date<='2026-05-31')].groupby('store').stockout_hours.mean().round(2)` | 2.17 |
| O19 | Pune mean stockout_hours 2026-05-01..2026-05-31 | `c[(c.date>='2026-05-01')&(c.date<='2026-05-31')].groupby('store').stockout_hours.mean().round(2)` | 2.21 |
| O19 | Bengaluru mean stockout_hours 2026-05-01..2026-05-31 | `c[(c.date>='2026-05-01')&(c.date<='2026-05-31')].groupby('store').stockout_hours.mean().round(2)` | 2.29 |
| O19 | Ahmedabad mean stockout_hours 2026-05-01..2026-05-31 | `c[(c.date>='2026-05-01')&(c.date<='2026-05-31')].groupby('store').stockout_hours.mean().round(2)` | 3.12 |
| O19 | Hyderabad mean stockout_hours 2026-05-01..2026-05-31 | `c[(c.date>='2026-05-01')&(c.date<='2026-05-31')].groupby('store').stockout_hours.mean().round(2)` | 3.70 |
| O22 | Pune revenue on 2026-05-17 (a Sunday) | `c[(c.store=='Pune')&(c.date=='2026-05-17')].revenue_inr.iloc[0]` | 560636.76 |
| R01 | Pune mean daily revenue 2026-04-01..2026-06-29 | `c.groupby('store').revenue_inr.mean().round(2)  (same as analysis/findings.md)` | 636358.55 |
| R01 | Ahmedabad mean daily revenue 2026-04-01..2026-06-29 | `c.groupby('store').revenue_inr.mean().round(2)  (same as analysis/findings.md)` | 782647.37 |
| R01 | Hyderabad mean daily revenue 2026-04-01..2026-06-29 | `c.groupby('store').revenue_inr.mean().round(2)  (same as analysis/findings.md)` | 893233.01 |
| R01 | Bengaluru mean daily revenue 2026-04-01..2026-06-29 | `c.groupby('store').revenue_inr.mean().round(2)  (same as analysis/findings.md)` | 931065.68 |
| R01 | Mumbai mean daily revenue 2026-04-01..2026-06-29 | `c.groupby('store').revenue_inr.mean().round(2)  (same as analysis/findings.md)` | 1064371.60 |

Cases without a figure (they check status, intent and fixed wording only): O03-O09, O10-O13, O20, O21.
