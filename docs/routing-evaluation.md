# Routing Evaluation Harness

F2 evaluates the active deterministic policy against a versioned, labeled task
corpus. Scenarios define hard requirements, deployment evidence, runtime signals,
expected eligibility/selection, and optional counterfactual outcomes. Replays use
the production capability filter and policy implementation.

Reports measure eligibility and selection agreement, constraint violations,
completion and deadline success, cost per accepted result, latency, failover
recovery, decision stability, outcome coverage, and uncertainty. Quality coverage
is explicitly zero until a credible labeled dataset exists; policy agreement is
not presented as model accuracy.

Each scenario removes candidates in turn to record counterfactual selections.
Versioned thresholds make the command fail when a policy change regresses:

```bash
python -m scripts.evaluate_routing
python -m scripts.evaluate_routing --output /tmp/routing-report.json
```

Policy changes must update or add evidence and commit a reviewed report. Changing
labels merely to make a regression pass is not evaluation.
