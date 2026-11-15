"""Part A: inspect and clean data/store_daily.csv.

Run from the repository root:  python scripts/clean_data.py
Reads   data/store_daily.csv                       (raw, never edited)
Writes  data/store_daily_clean.csv, analysis/cleaning_log.csv,
        analysis/data_quality_report.md
"""
import csv
import os
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pandas as pd

RAW = "data/store_daily.csv"
CLEAN = "data/store_daily_clean.csv"
LOG = "analysis/cleaning_log.csv"
REPORT = "analysis/data_quality_report.md"


def r2(x):
    """Round half-up to 2 decimals and return a Decimal."""
    return Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def store_bounds(df):
    """Per-store Q1, Q3, IQR, lower, upper of non-missing footfall (linear interpolation)."""
    out = {}
    for store, g in df.groupby("store"):
        s = g["footfall"].dropna()
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        out[store] = (q1, q3, iqr, q1 - 1.5 * iqr, q3 + 1.5 * iqr)
    return out


def main():
    os.makedirs("analysis", exist_ok=True)
    raw = pd.read_csv(RAW)

    # ------------------------------------------------------------------ inspection (raw)
    shape = raw.shape
    dtypes = raw.dtypes.astype(str).to_dict()
    nulls = raw.isna().sum().to_dict()
    n_dups = int(raw.duplicated().sum())
    ff_min, ff_max = raw["footfall"].min(), raw["footfall"].max()

    # ------------------------------------------------------------------ cleaning
    log = []
    # 1. exact duplicates, keep first
    df = raw.drop_duplicates(keep="first").copy().reset_index(drop=True)
    df["footfall"] = df["footfall"].astype(float)

    # 2. negative footfall -> missing
    for i in df.index[df["footfall"] < 0]:
        log.append((df.at[i, "store"], df.at[i, "date"], df.at[i, "footfall"], "", "negative_to_missing", i))
        df.at[i, "footfall"] = np.nan

    # 3. per-store IQR cap (bounds from non-missing values after steps 1-2)
    bounds = store_bounds(df)
    pre_cap = df.copy()
    for i, r in df.iterrows():
        if pd.isna(r["footfall"]):
            continue
        q1, q3, iqr, lo, hi = bounds[r["store"]]
        if r["footfall"] > hi or r["footfall"] < lo:
            new = hi if r["footfall"] > hi else lo
            new = r2(new)
            log.append((r["store"], r["date"], r["footfall"], new, "iqr_cap", i))
            df.at[i, "footfall"] = float(new)

    # 4. per-store median imputation (median of non-missing values after step 3)
    medians = df.groupby("store")["footfall"].median()
    for i in df.index[df["footfall"].isna()]:
        store = df.at[i, "store"]
        m = float(medians[store])
        log.append((store, df.at[i, "date"], "", m, "median_impute", i))
        df.at[i, "footfall"] = m

    # 5. revenue_inr and the other columns are untouched

    # ------------------------------------------------------------------ cleaning_log.csv
    # The log lists one row per change. A value that was negative and then imputed
    # gets both a negative_to_missing row and a median_impute row (two changes).
    def fmt(v):
        if v == "" or v is None:
            return ""
        return f"{float(v):.2f}" if not isinstance(v, Decimal) else f"{v:.2f}"

    order = {"negative_to_missing": 0, "iqr_cap": 1, "median_impute": 2}
    log_sorted = sorted(log, key=lambda t: (order[t[4]], t[0], t[1]))
    with open(LOG, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["store", "date", "old_footfall", "new_footfall", "rule"])
        for store, date, old, new, rule, _ in log_sorted:
            if rule == "negative_to_missing":
                w.writerow([store, date, int(old), "", rule])
            elif rule == "iqr_cap":
                w.writerow([store, date, int(old), fmt(new), rule])
            else:
                w.writerow([store, date, "", fmt(new), rule])

    # ------------------------------------------------------------------ feature columns
    # footfall written with 2 decimals where a rule changed it, as a whole number otherwise
    changed = {(s, d): n for s, d, _, n, rule, _ in log if rule in ("iqr_cap", "median_impute")}
    df["revenue_per_footfall"] = (df["revenue_inr"] / df["footfall"]).round(2)
    df["marketing_efficiency"] = (df["revenue_inr"] / df["marketing_spend_inr"]).round(2)
    ach = df["revenue_inr"] / df["daily_target_inr"] * 100
    df["achievement_pct"] = ach.round(2)
    df["shortfall_inr"] = (df["daily_target_inr"] - df["revenue_inr"]).round(2)
    dow = pd.to_datetime(df["date"]).dt.day_of_week
    df["weekend_flag"] = np.where(dow >= 5, "Yes", "No")
    df["performance_band"] = np.where(ach >= 100, "Excellent", np.where(ach >= 75, "Good", "Poor"))

    out = df.copy()
    out["footfall"] = [
        f"{changed[(s, d)]:.2f}" if (s, d) in changed else str(int(v))
        for s, d, v in zip(df["store"], df["date"], df["footfall"])
    ]
    out.to_csv(CLEAN, index=False)

    # ------------------------------------------------------------------ data_quality_report.md
    dedup = raw.drop_duplicates(keep="first").copy()
    dedup.loc[dedup["footfall"] < 0, "footfall"] = np.nan
    b = store_bounds(dedup)
    outliers = []
    for store, g in dedup.groupby("store"):
        q1, q3, iqr, lo, hi = b[store]
        for _, r in g.iterrows():
            if pd.notna(r["footfall"]) and (r["footfall"] < lo or r["footfall"] > hi):
                outliers.append((store, r["date"], int(r["footfall"]), lo, hi))

    dup_list = ", ".join(f"{r.store} {r.date}" for r in raw[raw.duplicated(keep="first")].itertuples())
    miss_list = ", ".join(f"{r.store} {r.date}" for r in raw[raw["footfall"].isna()].itertuples())
    L = []
    L.append("# Data quality report: data/store_daily.csv (raw file)\n")
    L.append("All figures below are computed on the **raw** file by `scripts/clean_data.py`.\n")
    L.append("## Shape\n")
    L.append(f"{shape[0]} rows by {shape[1]} columns.\n")
    L.append("## Data type and null count of every column\n")
    L.append("| column | dtype (pandas %s) | nulls |" % pd.__version__)
    L.append("|---|---|---|")
    for c in raw.columns:
        L.append(f"| {c} | {dtypes[c]} | {nulls[c]} |")
    L.append("")
    L.append(f"Exact duplicate rows: **{n_dups}** (every column identical to an earlier row).\n")
    L.append(f"Footfall minimum: **{ff_min:.0f}**; maximum: **{ff_max:.0f}**; missing footfall values: **{nulls['footfall']}**.\n")
    L.append("## Footfall bounds per store (IQR method)\n")
    L.append("Computed after removing the exact duplicates and after treating negative footfall as missing, "
             "using non-missing values only. Percentiles use linear interpolation, as `df.describe()` does.\n")
    L.append("| store | Q1 | Q3 | IQR | lower bound (Q1 - 1.5*IQR) | upper bound (Q3 + 1.5*IQR) |")
    L.append("|---|---|---|---|---|---|")
    for store in sorted(b):
        q1, q3, iqr, lo, hi = b[store]
        L.append(f"| {store} | {q1:.3f} | {q3:.3f} | {iqr:.3f} | {lo:.3f} | {hi:.3f} |")
    L.append("")
    L.append(f"Rows outside their store's bounds: **{len(outliers)}**.\n")
    L.append("| store | date | footfall | lower bound | upper bound |")
    L.append("|---|---|---|---|---|")
    for s, d, v, lo, hi in outliers:
        L.append(f"| {s} | {d} | {v} | {lo:.3f} | {hi:.3f} |")
    L.append("")
    L.append("## Decisions\n")
    L.append("Treatments were applied in this order: duplicates, negatives, extremes, missing values.\n")
    L.append("### 1. Exact duplicate rows\n")
    L.append("- **What I did:** removed the 3 exact duplicates (" + dup_list + "), keeping the first occurrence of each. 453 rows became 450 (5 stores x 90 days).\n"
             "- **Why:** a store has one row per day, so a second identical row would double count that day's revenue and footfall in every average. "
             "Keeping the first occurrence is safe because the copies are identical in every column.\n"
             "- **Raw file still contains:** all 3 duplicate rows, at the end of `data/store_daily.csv`. The raw file is never edited.\n")
    L.append("### 2. Negative values\n")
    L.append("- **What I did:** set the one negative footfall (Hyderabad 2026-04-21, -150) to missing, so it is then filled by the median step.\n"
             "- **Why not zero:** a store that sold goods that day cannot have had zero visitors, and a zero would drag the store's average and the revenue-per-footfall ratio. "
             "**Why not delete the row:** the row's revenue, target and stockout hours are valid and are needed for revenue and target questions.\n"
             "- **Raw file still contains:** the value -150.\n")
    L.append("### 3. Extreme values\n")
    L.append("- **What I did:** capped the 2 extreme footfall values at the nearest bound of their own store: Ahmedabad 2026-05-26 (9800 became 2281.38) and Mumbai 2026-04-09 (6100 became 2986.00).\n"
             "- **Why cap, not delete:** those days have real revenue (a busy day is genuine, only the footfall figure is implausible), so deleting the row would lose revenue. "
             "Capping keeps the row and stops one value from distorting the mean and the correlation. **Why per-store bounds:** stores differ in size, so one pooled bound would be wrong for both Pune and Mumbai.\n"
             "- **Raw file still contains:** 9800 and 6100.\n")
    L.append("### 4. Missing values\n")
    L.append("- **What I did:** filled each remaining missing footfall (the 4 blanks plus the 1 value made missing in step 2, so 5 in all) with the median of that store's non-missing footfall (after capping).\n"
             "- **Why the median, not the mean:** the median is not pulled by extreme days. **Why per store, not the all-store median:** store sizes differ (Pune about 1500, Mumbai about 2400). "
             "**Why not zero:** zero would be an invented, impossible value.\n"
             "- **Raw file still contains:** the 4 blank footfall cells (" + miss_list + ").\n")
    L.append("`revenue_inr` and every other column were left untouched.\n")
    with open(REPORT, "w") as f:
        f.write("\n".join(L))

    print("clean rows:", len(out), "| log rows:", len(log_sorted))
    for t in log_sorted:
        print(t[:5])


if __name__ == "__main__":
    main()
