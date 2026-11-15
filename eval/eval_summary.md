# Evaluation summary

Computed by `eval/run_eval.py` from `eval/eval_results.csv` (50 golden cases; LLM_MODE=mock, WEATHER_MODE=stub).

## Cost

- tokens_est: mean 27.98, maximum 58 (budget 150)
- total tool_calls: 32
- budget_exceeded cases: 0

## Latency (ms)

- mean 0.428, 90th percentile (linear interpolation) 0.435, maximum 7.967

## Quality

- overall pass rate: 50/50 = 100.00%
- total ungrounded_numbers: 0
- pass count per category:

| category | passed | cases |
|---|---|---|
| ambiguity | 4 | 4 |
| comparison | 5 | 5 |
| diagnostic | 1 | 1 |
| feedback | 2 | 2 |
| injection | 3 | 3 |
| inventory | 2 | 2 |
| lookup | 11 | 11 |
| out_of_range_date | 3 | 3 |
| out_of_scope | 2 | 2 |
| retry | 2 | 2 |
| synonym | 1 | 1 |
| target_vs_actual | 4 | 4 |
| typo | 2 | 2 |
| unresolved_date | 2 | 2 |
| unresolved_store | 2 | 2 |
| unsupported_metric | 2 | 2 |
| weather | 2 | 2 |

## Safety

- pass rate of the categories injection, unsupported_metric and out_of_scope: 7/7 = 100.00%
- non-answer replies (Safe Failure, Escalated, Clarification Needed) whose answer_text states an INR figure (computed from eval/eval_runs.jsonl): 0 (must be 0)
- .gitignore lists .env: yes
