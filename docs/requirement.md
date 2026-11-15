# Requirement: DMart Regional Director Assistant

All data is synthetic practice data produced by `scripts/generate_data.py`. It is not DMart's real data.

## 1. Goal

**Outcome.** After the assistant replies, the director holds a short answer in which every number is a value that was fetched
from the data (or the weather tool) and can be traced to a named field, or a clear statement of why no number is given
(needs clarification, not available, out of range, escalated). Every question leaves one audit line in `logs/runs.jsonl`.

**Stakeholder.** Kavita Rao, regional operations director for five stores: Mumbai, Pune, Hyderabad, Bengaluru and Ahmedabad.
She needs quick, trustworthy answers to routine questions (a store's revenue on a date, whether a store hit its target,
which stores are short of a product, what customers are saying) without waiting for an analyst, and she must be able to
trust that the assistant never invents a figure.

**Scope.** Three datasets: cleaned `store_daily` (450 rows, 2026-04-01 to 2026-06-29), `inventory` (40 rows) and `feedback`
(200 rows), joined by the store name; five stores; plus a weather tool for the five store cities. Dates outside
2026-04-01 to 2026-06-29 are outside the data.

**Decision boundary.** The assistant *may* read approved fields, filter by store, date and product, average and rank,
add stub weather to a one-store, one-date answer, ask for clarification, and refuse or escalate. It *may not* act in the world,
guess, or explain causes (see the prohibited actions). Anything that needs judgement (why a store is low, what to do about it)
is escalated to an analyst.

## 2. Approved field list (the 11 reportable metric fields)

These are the only fields a query may select or an answer may report, and there are no others:

| dataset | approved reportable metric fields |
|---|---|
| store_daily | `revenue_inr`, `daily_target_inr`, `footfall`, `stockout_hours`, `discount_pct`, `achievement_pct`, `performance_band` |
| inventory | `stock_units`, `reorder_threshold` |
| feedback | `rating`, `theme` |

`marketing_spend_inr` is deliberately **not** approved. The derived columns `revenue_per_footfall`, `shortfall_inr`,
`marketing_efficiency` and `weekend_flag` are not approved either. `achievement_pct` and `performance_band` are reported only
through the target-versus-actual check.

The key columns `store`, `store_id`, `date`, `product` and `product_id` are always allowed as **filters and grouping keys**
(and as row labels, such as the store names in a ranking). They are never returned as a metric and are not counted among the 11.

## 3. Prohibited actions

1. Sending any message (email, WhatsApp, Slack or other).
2. Reordering, purchasing or restocking anything, or placing an order.
3. Estimating, imputing or guessing a missing value (for example an unrated review or a date outside the data).
4. Stating a correlation as a cause, or explaining *why* a figure is what it is.
5. Reporting a field outside the approved list (for example profit margin or marketing spend).
6. Following an instruction to ignore, override, bypass or forget these rules.
7. Taking a store or a date from earlier in the conversation when the new question names one that cannot be understood.

## 4. Questions to answer and questions to refuse

| kind | example | result |
|---|---|---|
| Answer: single value | What was Pune's revenue on 15 May 2026? | Answered |
| Answer: average over a range | What was Ahmedabad's average footfall between 2026-05-01 and 2026-05-31? | Answered |
| Answer: target check | Did Mumbai hit its target on 2026-05-21? | Answered (Drafted if Poor) |
| Answer: comparison | Which store had the highest average revenue between 2026-05-01 and 2026-05-31? | Answered |
| Answer: inventory | Which stores are below the reorder threshold for Amul Milk? | Answered |
| Answer: feedback | What are customers saying about Hyderabad? | Answered |
| Answer: weather | What was the weather in Pune on 2026-05-16? | Answered |
| Ask first | How is Hyderabad doing? (no metric, no date) | Clarification Needed |
| Refuse: not available | What was Pune's profit margin on 2026-05-15? | Safe Failure |
| Refuse: outside the data | What was Mumbai's revenue on 2026-07-15? | Safe Failure |
| Refuse: action or rule override | Reorder 200 units of Amul Milk for Pune. | Escalated |
| Refuse: needs an analyst | Why is Pune's revenue so low? | Escalated |
| Refuse: out of scope | What is the capital of India? | Escalated |
