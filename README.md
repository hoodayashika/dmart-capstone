# DMart Regional Director Assistant: store diagnosis and a grounded analytics agent

All data is **synthetic practice data** written by `scripts/generate_data.py`. It is not DMart's real data.

## Purpose

Kavita Rao (regional operations director, five stores) believes Pune has the lowest revenue because of stockouts and is about to fund a
stock-availability programme. This repository (1) cleans the store data and tests that premise (Part A), (2) specifies a conversational
assistant for her routine questions (Part B), (3) builds that assistant so every number traces to a data field (Part C), and (4) adds a weather
tool, measures the assistant and makes a GO / NO-GO release decision (Part D).

**Headline result (Part A):** Pune ranks 4th of 5 by mean stockout hours (2.32 against 2.74 for all stores; Hyderabad is highest at 3.85), so the
premise is not supported. Pune's revenue is 26.14% below the all-store mean and its footfall 25.00% below, while revenue per footfall is only
1.52% below: the gap is a footfall gap, not a stockout gap. See `analysis/executive_summary.md`.

## Setup and run order

Python 3.9+ with `pandas` and `numpy` (`pip install -r requirements.txt`). Run everything from the repository root:

```
python scripts/generate_data.py      # writes data/store_daily.csv, inventory.csv, feedback.csv (never edit these afterwards)
python scripts/clean_data.py         # data/store_daily_clean.csv, analysis/cleaning_log.csv, analysis/data_quality_report.md
python scripts/analyze.py            # analysis/findings.md, analysis/executive_summary.md
python scripts/run_acceptance.py     # 20 acceptance cases -> outputs/acceptance_transcript.md, logs/runs.jsonl (20 lines)
python eval/run_eval.py              # eval/eval_results.csv, eval_runs.jsonl, eval_summary.md, docs/release_gate.md
python agent/run_agent.py            # optional: ask the assistant questions interactively
```

Before submitting, put your own name in `AUTHOR` at the top of `scripts/analyze.py` and re-run it (it sets the author line of the executive summary).

## Free offline path

Everything graded runs offline: `LLM_MODE=mock` (rule-based interpreter and fixed answer templates, no language model), `WEATHER_MODE=stub`
(deterministic formula) and a local in-memory SQLite database built from the CSV files. No account or API key is needed. Optional and ungraded:
a hosted database, a hosted language model, and `WEATHER_MODE=live`, which calls the free Open-Meteo archive API (needs `requests`; the branch is in
`tools/weather.py`, no live data is committed). Environment variables: `SIMULATE_DB_FAILURES=<n>`, `AGENT_LOG_PATH`, `WEATHER_MODE`.

## Repository layout

```
README.md  .gitignore  requirements.txt
data/       store_daily.csv  inventory.csv  feedback.csv  store_daily_clean.csv
scripts/    generate_data.py  clean_data.py  analyze.py  run_acceptance.py
analysis/   data_quality_report.md  cleaning_log.csv  findings.md  executive_summary.md
docs/       requirement.md  data_context.md  agent_spec.md  release_gate.md
agent/      understand.py  fetch.py  answer.py  run_agent.py
tools/      weather.py
tests/      weather_tool_tests.md
outputs/    acceptance_transcript.md
logs/       runs.jsonl
eval/       golden_set.csv  golden_set_derivation.md  run_eval.py  eval_results.csv  eval_runs.jsonl  eval_summary.md
```

## Rounding method

Every average is computed with integer-cent arithmetic: SQL returns `COUNT(metric)` and `SUM(CAST(ROUND(metric * 100) AS INTEGER))` per store, and Python divides
with the `decimal` module and rounds half-up to 2 decimals.

## Results at a glance

- Part A: cleaned file has 450 rows and no missing values; cleaning log has 1 negative_to_missing, 2 iqr_cap and 5 median_impute rows.
- Part C: all 20 acceptance cases return the required status, intent and content (`outputs/acceptance_transcript.md`).
- Part D: see `eval/eval_summary.md` and `docs/release_gate.md` (the decision is produced by `eval/run_eval.py` from the measured numbers).

## Known limitations

- The interpreter is rule-based: it understands the closed vocabulary and date grammar in `docs/agent_spec.md` and asks for clarification or
  escalates otherwise. Phrasing outside those lists may be treated as out of scope.
- Where the brief left a detail open I made a choice and wrote it in the spec: an unmatched named store counts as "naming a store" for the comparison rule;
  a resolved store is ignored by comparison; an inventory question that names a store stores that store in context; a weather-only question whose tool call fails is a Safe Failure.
- Data is synthetic and small (5 stores, 90 days, 40 inventory rows, 200 feedback rows); the golden set (50 cases) is my own, so a GO shows the specified behaviour holds on those cases, not that the assistant is correct for every question.
- Stub weather is a formula, not real weather. Inventory is a single snapshot with no dates. Part A shows association, not cause; its hypotheses are unconfirmed.
- Latency figures depend on the machine that ran the evaluation.

## Iteration-2 backlog (prioritised)

1. **Trend questions (week-over-week and month-over-month).**
   *Input:* "How did Pune's revenue move week over week in May?" *Output:* a per-week table of average revenue with the change, every value traceable to `revenue_inr`.
   *Success:* each figure equals an independent pandas calculation to 0.01; `ungrounded_numbers` stays 0; no cause is stated. *Failure behaviour:* a period with no data returns Safe Failure naming the available range; a "why" question still escalates to an analyst.
2. **Deeper follow-up context ("and the week before?", "same for Mumbai").**
   *Input:* a short follow-up that changes one entity. *Output:* the previous question re-run with that entity changed. *Success:* at least 95% of a follow-up test set resolves to the intended entities, and unresolved names are never filled from context. *Failure behaviour:* when more than one reading is plausible, ask which one (Clarification Needed) instead of guessing.
3. **Hosted PostgreSQL in place of local SQLite.**
   *Input:* a connection string kept in an untracked `.env`. *Output:* identical answers from the hosted database. *Success:* the 50-case golden set gives the same pass/fail results and the same numbers as SQLite. *Failure behaviour:* connection errors use the same 3-attempt retry and end in Escalated, never in an invented figure.
4. **Optional language-model interpreter behind the same entity contract.**
   *Input:* the question and context. *Output:* the same entity dictionary as `understand`. *Success:* no drop in the golden-set pass rate, and every number still comes from fetched data. *Failure behaviour:* an invalid or low-confidence parse falls back to the rule-based interpreter.
