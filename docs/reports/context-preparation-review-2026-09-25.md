# Candidate-specific context preparation review

Date: 2026-09-25  
Scope: CTX-001 offline context fitting only. No provider calls or private inputs.

## Review result

The CTX-001 slice meets its bounded acceptance criteria. The review examined
`backend/context/contracts.py`, `backend/context/preparation.py`, ADR-017 and
`tests/test_context_preparation.py` against Phase 4's candidate-specific fitting
and fallback requirements.

- Candidate profile, capacity evidence reference, output reserve, safety margin,
  counter revision and template revision are returned with the prepared result.
  The injected counter must match the profile's counter/template identity.
- Required segments, including system policy, cannot be trimmed. Required
  content overflow raises `ContextOverflow`; no partial prompt is returned.
- Optional fitting is reproducible: exact duplicates merge only when role and
  declared origin also match, then low-priority sources are dropped first, with
  later position winning ties. Each removal is recounted.
- System-role content is restricted to mandatory policy. Assistant-role content
  must be explicitly marked as assistant history. The trust/origin label is
  provenance, not authorization or a truth claim.
- Results retain included and excluded source IDs/revisions, exclusion reasons,
  count method and confidence, capacity evidence and a SHA-256 digest of the
  structured message payload.
- Fallback behavior is correctly expressed as a new call to `prepare_context`
  with the fallback profile and counter. Synthetic tests prove counters may
  produce different selected context and digest.

No correctness issue remains within this boundary. The implementation is a
standalone library: it does not authorize sources, persist conversations,
construct task context, bind the result to inference dispatch, verify tokenizer
artifacts, or prove a production capacity limit. Those remain explicit CTX-002
through CTX-004 work; Phase 4 is not complete.

## Verification

```text
ruff check backend tests scripts: passed
mypy backend tests scripts: passed, 102 source files
compileall -q backend tests scripts: passed
pytest -q -m 'not integration': 377 passed, 8 deselected
ruff format backend/context tests/test_context_preparation.py: clean
git diff --check: passed
```

Full pytest ran outside the sandbox because existing subprocess tests stall
under sandbox stream restrictions. No external integration tests, live services,
or GPU certification ran.
