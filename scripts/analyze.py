"""Part A: test Kavita's premise on the cleaned data.

Run from the repository root:  python scripts/analyze.py
Reads   data/store_daily_clean.csv (plus data/store_daily.csv and data/feedback.csv for two side facts)
Writes  analysis/findings.md and analysis/executive_summary.md
"""
import numpy as np
import pandas as pd

AUTHOR = "YASHIKA H"


def corr(d, a, b):
    return float(np.corrcoef(d[a], d[b])[0, 1])


def main():
    c = pd.read_csv("data/store_daily_clean.csv")
    assert len(c) == 450
    fb = pd.read_csv("data/feedback.csv")
    raw = pd.read_csv("data/store_daily.csv").drop_duplicates()
    raw_nm = raw.dropna(subset=["footfall"])

    g = c.groupby("store")
    tab = pd.DataFrame({
        "rev": g["revenue_inr"].mean(),
        "ff": g["footfall"].mean(),
        "so": g["stockout_hours"].mean(),
        "rpf": g["revenue_inr"].sum() / g["footfall"].sum(),
        "ach": g["achievement_pct"].mean(),
        "poor": g["performance_band"].apply(lambda s: int((s == "Poor").sum())),
    })
    allrow = {
        "rev": c["revenue_inr"].mean(), "ff": c["footfall"].mean(), "so": c["stockout_hours"].mean(),
        "rpf": c["revenue_inr"].sum() / c["footfall"].sum(), "ach": c["achievement_pct"].mean(),
        "poor": int((c["performance_band"] == "Poor").sum()),
    }
    pune = c[c["store"] == "Pune"]

    # ranking by mean stockout hours (highest first)
    rank = tab["so"].sort_values(ascending=False)
    pune_rank = list(rank.index).index("Pune") + 1

    r_all_so = corr(c, "revenue_inr", "stockout_hours")
    r_all_ff = corr(c, "revenue_inr", "footfall")
    r_pu_so = corr(pune, "revenue_inr", "stockout_hours")
    r_pu_ff = corr(pune, "revenue_inr", "footfall")
    r_raw_ff = corr(raw_nm, "revenue_inr", "footfall")

    gap_rev = (1 - tab.loc["Pune", "rev"] / allrow["rev"]) * 100
    gap_ff = (1 - tab.loc["Pune", "ff"] / allrow["ff"]) * 100
    gap_rpf = (1 - tab.loc["Pune", "rpf"] / allrow["rpf"]) * 100

    pune_theme = fb[fb["store"] == "Pune"]["theme"].value_counts()
    top_theme = pune_theme.sort_index().sort_values(ascending=False, kind="stable").index[0]
    pune_target = int(pune["daily_target_inr"].iloc[0])
    mum_target = int(c[c["store"] == "Mumbai"]["daily_target_inr"].iloc[0])
    pune_mkt = pune["marketing_spend_inr"].mean()
    mum_mkt = c[c["store"] == "Mumbai"]["marketing_spend_inr"].mean()

    L = []
    L.append("# Findings: Pune and the stockout premise\n")
    L.append("Source: `data/store_daily_clean.csv` (450 rows = 5 stores x 90 days, 2026-04-01 to 2026-06-29). Synthetic practice data.\n")
    L.append("## Store table\n")
    L.append("| store | mean daily revenue (INR) | mean footfall | mean stockout hours | revenue per footfall (INR) | mean achievement_pct | days in Poor band |")
    L.append("|---|---|---|---|---|---|---|")
    for s in tab.index:
        t = tab.loc[s]
        L.append(f"| {s} | {t.rev:.2f} | {t.ff:.2f} | {t.so:.2f} | {t.rpf:.2f} | {t.ach:.2f} | {int(t.poor)} |")
    L.append(f"| All stores | {allrow['rev']:.2f} | {allrow['ff']:.2f} | {allrow['so']:.2f} | {allrow['rpf']:.2f} | {allrow['ach']:.2f} | {allrow['poor']} |")
    L.append("\nRevenue per footfall is each store's total revenue divided by its total footfall.\n")

    L.append("## Premise test\n")
    L.append("Premise: *Pune is the lowest-revenue store because of stockouts.* If it were true, Pune should have the most stockout hours.\n")
    L.append("Ranking of the five stores by mean stockout hours (highest first):\n")
    for i, (s, v) in enumerate(rank.items(), 1):
        L.append(f"{i}. {s}: {v:.2f} hours")
    L.append("")
    L.append(f"**Answer: no.** Pune ranks {pune_rank}th of 5 by mean stockout hours ({tab.loc['Pune','so']:.2f} against an all-store mean of "
             f"{allrow['so']:.2f}). Hyderabad is highest ({tab.loc['Hyderabad','so']:.2f}). "
             "The premise \"Pune has the most stockouts\" is **not supported** by the data.\n")

    L.append("### Correlations (Pearson)\n")
    L.append("| pair | rows | r |")
    L.append("|---|---|---|")
    L.append(f"| revenue_inr vs stockout_hours | all 450 | {r_all_so:.3f} |")
    L.append(f"| revenue_inr vs footfall | all 450 | {r_all_ff:.3f} |")
    L.append(f"| revenue_inr vs stockout_hours | Pune 90 | {r_pu_so:.3f} |")
    L.append(f"| revenue_inr vs footfall | Pune 90 | {r_pu_ff:.3f} |")
    L.append(f"| revenue_inr vs footfall, **before cleaning** (deduplicated raw rows with non-missing footfall, negative and extreme values still in) | {len(raw_nm)} | {r_raw_ff:.3f} |")
    L.append("")
    L.append(f"Cleaning changed the revenue-footfall correlation from {r_raw_ff:.3f} to {r_all_ff:.3f}: the impossible -150 and the two extreme values (6100, 9800) were hiding the real relationship.\n")
    L.append("Correlation does not establish causation: these figures show how the variables move together, not that one produces the other.\n")

    L.append("## Facts, Insights, Hypotheses\n")
    L.append("### Facts (numbers straight from the data)\n")
    L.append(f"- Pune's mean daily revenue is INR {tab.loc['Pune','rev']:.2f}, the lowest of the five stores; the all-store mean is INR {allrow['rev']:.2f}.")
    L.append(f"- Pune's mean footfall is {tab.loc['Pune','ff']:.2f} against {allrow['ff']:.2f} for all stores.")
    L.append(f"- Pune's mean stockout hours are {tab.loc['Pune','so']:.2f}, ranked {pune_rank}th of 5; Hyderabad has {tab.loc['Hyderabad','so']:.2f}.")
    L.append(f"- Pune's revenue per footfall is INR {tab.loc['Pune','rpf']:.2f} against INR {allrow['rpf']:.2f} for all stores.")
    L.append(f"- Pune had {int(tab.loc['Pune','poor'])} of {allrow['poor']} Poor-band days in the whole data set.")
    L.append(f"- Pune's daily target is INR {pune_target} and Mumbai's is INR {mum_target}.")
    L.append("")
    L.append("### Insights (interpretations)\n")
    L.append(f"1. Pune's revenue is {gap_rev:.2f}% below the all-store mean and its footfall is {gap_ff:.2f}% below; revenue per footfall is only {gap_rpf:.2f}% below. "
             "Almost the whole revenue gap is therefore a footfall gap, not a stockout (or basket) gap.")
    L.append(f"2. Revenue is somewhat lower on high-stockout days (r = {r_pu_so:.3f} in Pune) but footfall moves with revenue far more strongly (r = {r_pu_ff:.3f} in Pune, {r_all_ff:.3f} across all rows); "
             "a stockout programme would address the weaker of the two relationships, and Pune does not even have the most stockouts.")
    L.append(f"3. Pune's target (INR {pune_target}) is only {(1 - pune_target / mum_target) * 100:.1f}% below Mumbai's, while Pune's revenue is "
             f"{(1 - tab.loc['Pune','rev'] / tab.loc['Mumbai','rev']) * 100:.1f}% below Mumbai's, so the target is not scaled to Pune's footfall, which is why Pune sits in the Poor band on {int(tab.loc['Pune','poor'])} days.")
    L.append("")
    L.append("### Hypotheses (unconfirmed)\n")
    L.append("1. **Unconfirmed:** Pune's low footfall comes from a smaller or more competitive catchment area. "
             "*Data needed:* catchment population, competitor store locations and store floor area per city.")
    L.append(f"2. **Unconfirmed:** pricing perception keeps shoppers away (the most frequent Pune feedback theme is {top_theme}). "
             "*Data needed:* price comparison against nearby competitors and the share of feedback by theme over time, with more than 40 comments.")
    L.append(f"3. **Unconfirmed:** lower local marketing contributes to lower footfall (Pune spends INR {pune_mkt:.0f} a day on average against INR {mum_mkt:.0f} in Mumbai). "
             "*Data needed:* campaign-level spend and a before/after test of footfall.")
    with open("analysis/findings.md", "w") as f:
        f.write("\n".join(L) + "\n")

    # ------------------------------------------------------------------ executive summary
    ES = f"""# Executive Summary

**Dataset:** DMart synthetic store data (5 stores, 450 daily rows) | **Period:** 2026-04-01 to 2026-06-29 | **Author:** {AUTHOR}

**Headline:** Pune's low revenue is a footfall gap, not a stockout gap. Do not fund the Pune stock-availability programme yet.

**Magnitude:** Pune's revenue is {gap_rev:.2f}% below the all-store mean daily revenue and its footfall is {gap_ff:.2f}% below the all-store mean footfall. Revenue per footfall is only {gap_rpf:.2f}% below the all-store figure (Pune {tab.loc['Pune','rpf']:.2f} against {allrow['rpf']:.2f}).

**What is driving it and what is not:** Footfall tracks revenue closely (r = {r_pu_ff:.3f} in Pune). Stockouts do not account for Pune's gap: it ranks {pune_rank}th of 5 ({tab.loc['Pune','so']:.2f} hours; Hyderabad highest at {tab.loc['Hyderabad','so']:.2f}), and revenue vs stockout hours is only r = {r_pu_so:.3f} in Pune. Correlation is not causation.

**Supporting facts:**
- Pune had {int(tab.loc['Pune','poor'])} of {allrow['poor']} Poor-band days.
- Pune's mean achievement is {tab.loc['Pune','ach']:.2f}%.
- Pune's target is INR {pune_target}, close to Mumbai's INR {mum_target}, despite far lower footfall.

**Open hypotheses (unconfirmed):** (1) smaller or more competitive catchment: needs catchment and competitor data; (2) price perception: needs competitor price data; (3) lower local marketing: needs campaign-level spend.

**Recommendation:** The Regional Operations Director should pause the stock programme and have the Pune Store Manager and Marketing Lead run a footfall diagnosis (catchment, competitors, pricing), reporting in 30 days.
"""
    words = len(ES.split())
    assert words <= 250, words
    with open("analysis/executive_summary.md", "w") as f:
        f.write(ES)
    print("words in executive summary:", words)


if __name__ == "__main__":
    main()
