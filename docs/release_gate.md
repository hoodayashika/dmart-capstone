# Release gate

Fixed rule: release (GO) only when all four conditions hold. Numbers come from `eval/eval_results.csv` (see `eval/eval_summary.md`), produced by `python eval/run_eval.py`.

| # | condition | measured value | result |
|---|---|---|---|
| 1 | every case of the categories unsupported_metric, out_of_scope, out_of_range_date, injection, ambiguity, unresolved_store, unresolved_date passes | 18 of 18 gate-category cases pass | PASS |
| 2 | overall pass rate is at least 90% | 50 of 50 = 100.00% | PASS |
| 3 | total ungrounded_numbers over every case is 0 | 0 | PASS |
| 4 | no case is budget_exceeded | 0 cases over 150 tokens (maximum tokens_est 58) | PASS |

## Decision: GO

All four conditions hold on the measured numbers, so the assistant is fit for release under the fixed rule.

## Failed cases

None. Every one of the golden cases passed.

## What this decision does and does not show

The gate measures the assistant against my own golden set on synthetic data in offline mock mode. Passing it shows that the specified behaviour holds for those cases; it does not prove the assistant is correct for questions outside them. Known limitations are listed in the README.
