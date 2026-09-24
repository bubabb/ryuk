# ADR-012: one workflow budget across router attempts

Status: implemented for offline single-task workflows, 2026-09-15.

A `WorkflowBudget` is created once for a workflow execution and passed through
all router attempts. It owns one monotonic deadline, maximum attempt count, and
optional output-token ceiling. Router availability checks, backoff, and adapter
generation use the minimum of the task deadline and this budget's remaining
seconds. Each actual available deployment execution consumes one attempt; an
unavailable or circuit-open deployment does not. Retry policies cannot mint a
new budget or reset consumed attempts.

Output tokens are accounted for after a result returns. If the ceiling is
exceeded, the result is not accepted and the terminal failure includes the
attempt history. The provider call may already have produced output, so this is
an accounting boundary rather than a way to interrupt provider generation.
Unknown provider usage does not falsely count as zero. Cost and input-token
budgets remain future additions and must use the same shared object.

Budget exhaustion is `workflow_budget_exceeded`; a timeout while an in-flight
operation consumes the shared deadline and is `deadline_exceeded`. Both retain
attempt records. The router's existing `ExecutionPolicy.max_attempts` remains a
local safety ceiling; the workflow budget is the outer ceiling and may be
smaller. A shared budget is per execution and never persisted as a fresh budget
on retry or failover.

This contract is offline-only until workflow dispatch exists. No public API
creates budgets yet. WF-005 must bind exactly one budget to one stored workflow
execution and persist its configured limits and consumption without exposing
prompts or output content.
