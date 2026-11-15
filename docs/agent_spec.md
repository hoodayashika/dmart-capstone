# Agent specification

Default mode: `LLM_MODE=mock` (rule-based interpreter and fixed answer templates, no language model) and `WEATHER_MODE=stub`.
Implemented in `agent/understand.py` (Interpret), `agent/fetch.py` (Validate, Query, Calculate), `agent/answer.py` (Synthesize, Ground)
and `agent/run_agent.py` (Route, Record, orchestration).

## 1. Pipeline

| # | step | what it does | deterministic / generative | technique |
|---|---|---|---|---|
| 1 | Interpret | Turns the question into intent, store, metric, date or range, product, weather flag, confidence and missing entities | **generative** step of the design, implemented without a model | rule-based interpreter: word lists, a closed date grammar and `difflib.SequenceMatcher` for store typos |
| 2 | Route | Chooses python, sql, weather, python+weather or none from the intent and entities, and applies session context | deterministic | intent-to-route table (section 2) |
| 3 | Validate | Checks table and columns against the 11 approved fields before any query runs (placed here, before Query, by design) | deterministic | `validate_query` whitelist; values only as `?` parameters; sort direction only ASC or DESC |
| 4 | Query | Runs the data query (Python function or SQLite SQL) with retries | deterministic | `sqlite3`, `?` placeholders, at most 3 attempts per query |
| 5 | Calculate | Averages, ranks, achievement checks | deterministic | integer-cent sums divided with `decimal`, ROUND_HALF_UP to 2 decimals; ties by store name |
| 6 | Synthesize | Writes the reply | **generative** step of the design, implemented without a model | fixed answer templates with the stated number formats |
| 7 | Ground | Builds evidence and `grounded_values` from fetched values, counts `ungrounded_numbers` | deterministic | `grounded_values` is built from fetched or computed values, never by scanning the finished text; the count scans the text afterwards as a check |
| 8 | Record | Appends one JSON line per question to the log | deterministic | `logs/runs.jsonl` (path read from `AGENT_LOG_PATH` on every call) |

## 2. Intents and routes

| intent | example question | route |
|---|---|---|
| lookup | What was Pune's revenue on 15 May 2026? | Python function for one store and one date; SQL for an average over a range |
| target_vs_actual | Did Pune hit its target on 2026-05-16? | Python function |
| comparison | Which store had the highest average revenue between 2026-05-01 and 2026-05-31? | SQL |
| inventory | Which stores are below the reorder threshold for Amul Milk? | SQL |
| feedback | What are customers saying about Hyderabad? | SQL |
| weather | What was the weather in Pune on 2026-05-16? | weather tool (`get_weather`) |
| unsupported_metric | What was Pune's profit margin on 2026-05-15? | none |
| out_of_scope | What is the capital of India? / Reorder 200 units of Amul Milk for Pune | none |
| diagnostic | Why is Pune's revenue so low? | none |

A weather word added to a one-store, one-date lookup or target_vs_actual question adds the weather (route `python+weather`).
It is ignored for comparison, inventory, feedback and for a range lookup.

**Intent order** (first match wins): (1) override or prohibited-action words (ignore, disregard, override, bypass, forget, send,
email, whatsapp, purchase, buy, restock, "place an order", and order/reorder used as an imperative unless followed by threshold, level
or point) give out_of_scope; (2) a column outside the approved 11 (profit, margin, marketing, cost, expense, shortfall, efficiency,
weekend, "per footfall", "per visitor") gives unsupported_metric; (3) why, trend, reason, cause give diagnostic; (4) a product name or the
words reorder or inventory give inventory; (5) feedback, review, rating, theme or "customers say/saying" give feedback; (6) "target" with
hit, met, miss, beat, exceed, achieve, reach, below, above, against, versus or "fall short", or "achievement", or "performance band" give
target_vs_actual; (7) which, highest, lowest, best or worst with no store named gives comparison (a store that was named but could not be
matched counts as named); (8) a metric gives lookup; (9) a weather word with no metric gives weather; (10) a store and/or a date named
(resolved or not) with no metric and no weather word gives lookup, or target_vs_actual when the last stored question was a target check;
(11) anything else is out_of_scope. Underscores count as spaces and every keyword counts in singular and plural.

## 3. Handling rules

**Stores.** An exact store name matches case-insensitively anywhere (MUMBAI works) with confidence 1.0; Bangalore is an explicit alias of
Bengaluru with confidence 1.0. A misspelling is fuzzy-matched with `SequenceMatcher` against the five names and the score becomes the
confidence, but only for a candidate word: at least 5 letters, capitalised or carrying 's, not the first word of the question (unless it
carries 's), and neither a keyword, a stop word, a word of a recognised product name nor one of the brief's proper nouns. A score of 0.7
or more resolves (Bengalore 0.78, Bangalor 0.71, Punee 0.89, Hydrabad's 0.94, Mumbay 0.83); lower does not (Banglore 0.59). A candidate
below 0.7 is an **unresolved named store** (confidence 0.4) when it carries 's or follows and, or, vs, versus, than or for (whatever else
resolved), or, when no store resolved at all, when it follows about, in or at or the question has a metric, weather word or date.
Brand or persona nouns (DMart, Avenue, Supermarts, Kavita, Rao) with 's or after for, about, in or at are unresolved when no store
resolved. An unresolved store is never replaced from context.

**Metrics.** revenue, sales, turnover, earnings give `revenue_inr`; target gives `daily_target_inr`; footfall and visitors give `footfall`;
stockout gives `stockout_hours`; discount gives `discount_pct`. The list is closed.

**Dates.** Closed grammar: `YYYY-MM-DD` (exactly 4-2-2 digits, a real calendar date), `D Month YYYY` (full month name, any case), `yesterday`
and `between <date> and <date>` (inclusive, start not after end). `AS_OF_DATE = 2026-06-30`, so yesterday is 2026-06-29. Anything else that
looks like a date or a period (20260515, 2026-5-15, 2026-02-30, May 15, 2026, 15 Jun 2026, 15th May 2026, today, last week, Q1, a month or
weekday name, a bare year, a second date outside between ... and ..., a range for target_vs_actual or weather) is an **unresolved named date**
(confidence 0.4, Clarification Needed, never filled from context). A weekday that names the weekday of the one valid date is ignored; a
plural weekday beside a valid between range is ignored. lowercase may and march count as months only after in, on, of, during, since, for,
from, until, till, by, to, through, throughout, before, after, within or over; a capitalised May before I, we, you or be is the verb.
Frequency words (daily, weekly, monthly, per day) are not date phrases. A question with no date phrase takes the date from context.
inventory and feedback drop any date.

**Confidence.** The minimum over the entities the intent uses (its required entities, plus a store named in the question): 1.0 for an exact
store, alias, exact product, synonym or any date resolved by the grammar and for a value from context; the fuzzy similarity for a fuzzy
store; 0.4 for a missing required entity, an unresolved named store or date, or an ambiguous question. **Below 0.7 the agent asks for
clarification** instead of answering. A question with no entities has confidence 1.0.

**Ambiguity.** Two different stores or two different metrics among the entities the intent uses give Clarification Needed (confidence 0.4)
and a question asking which one. There is no first-match-wins. (A resolved store is not used by comparison, and a metric is not used by
target_vs_actual, inventory or feedback.)

**Session context.** An entity named in the question overrides the stored one. A required entity left out is taken from the last resolved
value in the same session (store, metric, date or range, product). Only required entities are taken, so a comparison never takes a store.
An unresolved named store or date and an ambiguous pair are never replaced from context; a range in context is never carried into
target_vs_actual or weather (it is an unresolved named date there). Context never crosses sessions. unsupported_metric, diagnostic and
out_of_scope do not update the context; every other question, even one ending in Clarification Needed, stores the used entities it resolved.
target_vs_actual stores store and date only and marks the session so that a bare follow-up naming only a store or a date is a target check again.

**Required entities per intent.**

| intent | required | optional |
|---|---|---|
| lookup | store, metric, date or range | none |
| target_vs_actual | store, one date | none |
| comparison | metric, date or range | none |
| inventory | product | store (restricts the list) |
| feedback | store | none |
| weather | store, one date | none |
| unsupported_metric, out_of_scope, diagnostic | none | none |

**Data rules.** A date or part of a range outside 2026-04-01 to 2026-06-29 is a Safe Failure that states the range. Comparison ranks the
per-store average highest first (default and "highest") or lowest first ("lowest"); best and worst follow the metric (on `stockout_hours`
lower is better). Ties at 2 decimals sort by store name. inventory lists stores where `stock_units` is strictly below `reorder_threshold`;
none below is an Answered fixed message. feedback gives the average rating over rated rows, the rated count, the total count and the most
frequent theme (ties by theme name).

**Number formats.** Money `INR 623845.00`; percentages 2 decimals with %; rating, footfall and stockout hours 2 decimals; counts as integers;
weather values with one decimal and rain as `0.0 mm`. Averages are exact means rounded half-up to 2 decimals.

## 4. Status decision table

| status | exact condition |
|---|---|
| Answered | the intent was understood, the entities are complete and confident, the date is in range, the queries succeeded, the numbers are grounded, and no alert fired |
| Drafted | the answer is composed but held for human approval because an alert fired: a target_vs_actual result in the Poor band (achievement below 75%) |
| Clarification Needed | confidence below 0.7, a required entity missing, an unresolved named store or date, or two different stores or metrics |
| Escalated | the intent is out_of_scope (including prohibited actions and rule overrides) or diagnostic, or a data query failed 3 attempts |
| Safe Failure | a field outside the approved list (unsupported_metric), a date outside the data range, or no record found for the product, store or date (also: the weather tool returned an error for a weather-only question) |

**Precedence (first rule that applies decides):** (1) the intent itself: unsupported_metric gives Safe Failure, out_of_scope and diagnostic
give Escalated; (2) a missing required entity, unresolved named store or date, two stores or metrics, or confidence below 0.7 gives
Clarification Needed; (3) for lookup, target_vs_actual, comparison and weather, a date or range outside the data gives Safe Failure;
(4) data queries: 3 failed attempts give Escalated, no record found gives Safe Failure; (5) otherwise Drafted if the alert fired, else Answered.
A reply never states a correlation as a cause and never contains a number that was not fetched.

## 5. Escalation and retry

- A failed data query is retried. **A query gets at most three attempts** (the first try plus two retries).
- Exhausting the three attempts gives **Escalated**; the reply says so in words (three attempts) and contains no figure.
- `attempts` in the log is the highest attempt count among the question's data queries, and 0 when no data query ran. A retry is not an extra
  `tool_calls` entry. An approved-field violation is not retried.
- `SIMULATE_DB_FAILURES=<n>` makes the first n attempts of every query fail (used by A19 with 2 failures and A20 with 3).

## 6. Success criteria

1. Every number in an answer appears in the fetched data, the tool result or a quoted constant: `ungrounded_numbers` is 0 for every reply of every status.
2. 100% of queries pass the approved-field check before they run; no user text is ever joined into SQL.
3. Each of the 20 acceptance cases returns the required status, intent and content (exact to 0.01).
4. A non-answer reply (Safe Failure, Escalated, Clarification Needed) never states an INR figure.
5. An unresolved named store or date is never filled from context.
6. Every question writes one complete log line; every reply uses at most 150 tokens (`tokens_est`).
7. The release gate in `docs/release_gate.md` returns GO: gate categories all pass, overall pass rate at least 90%, ungrounded 0, no budget overrun.

**Completion states:** every question ends in exactly one of Answered, Drafted, Clarification Needed, Escalated or Safe Failure, and is logged.

## 7. Test-case categories (Part D)

lookup, typo, synonym, ambiguity, target_vs_actual, comparison, inventory, feedback, weather, unsupported_metric, out_of_scope, injection,
out_of_range_date, unresolved_store, unresolved_date, diagnostic and retry.
