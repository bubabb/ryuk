# Audit Evaluation

Run `python -m scripts.evaluate_audit`. The versioned corpus currently checks
policy mechanics for clean output, missing citations, secret leakage, and prompt
injection language. CI requires 100% expected-action agreement and zero false
accepts.

This four-case corpus is deliberately labeled as mechanics coverage. It does
not establish factual-audit accuracy or authorize a model auditor in production.
That requires representative labeled claims, blinded generator/auditor splits,
independent evidence, false-positive/false-negative analysis, and demonstrated
incremental value over deterministic validation.
