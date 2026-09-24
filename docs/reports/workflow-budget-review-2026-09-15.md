# WF-004 offline workflow budget review

`WorkflowBudget` now provides one deadline, attempt ceiling, and optional output
-token ceiling shared by all router attempts. Availability probing and adapter
generation use the same remaining time. Circuit-open/unavailable deployments
do not consume attempt reservations; each actual execution consumes exactly one.
Retry failover cannot reset the attempt counter or mint a nested budget.

Focused tests cover invalid limits, monotonic remaining time, one-budget versus
larger router policy, shared timeout behavior, and output-token accounting.
The budget is intentionally not a dollar-cost budget and unknown token usage is
not treated as zero.

Validation:

- Full offline suite: **286 passed, 8 external integrations deselected**.
- Ruff, Mypy, compileall, and `git diff --check` passed.

Review found no blocking issue in this bounded contract. The budget is not yet
persisted or exposed by workflow APIs. WF-005 must construct one budget for a
stored workflow execution, pass it through dispatch, persist configured limits
and consumption, and distinguish accepted inference results from validated
workflow completion. Live certification remains pending.
