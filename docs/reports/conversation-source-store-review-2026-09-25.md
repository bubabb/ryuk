# Conversation and source-store review

Date: 2026-09-25  
Scope: CTX-002 offline SQLite conversation/source store and context assembly.
No provider calls or private inputs were used.

## Review result

The bounded CTX-002 implementation meets its offline acceptance criteria. The
review examined `backend/context/contracts.py`, `store.py`, `builder.py`, ADR-018
and `tests/test_context_store.py` for scope, authorization order, immutability,
restart and concurrent-write behavior.

- Conversation reads are tenant-scoped. Private conversations require their
  owner; project conversations require current membership. Conversation and
  source creation require current project membership.
- Source records are separate from ordered messages, immutable by source
  revision through the store API, SHA-256 checked on read and referenced with a
  composite tenant/source/revision foreign key.
- Private sources cannot be attached to project-visible conversations. All
  selected sources must match the conversation's project and current access
  rules. Membership is rechecked during context building.
- The builder uses server-configured required policy, requires at least one
  required objective/criteria source, authorizes every selected reference
  before loading its content, and fails the entire build on any unauthorized
  source instead of silently producing partial context.
- Recent messages retain chronological order, are bounded to the most recent
  100 records, and their source visibility is checked before content is read.
  Concurrent writers allocate unique sequence numbers in SQLite transactions.
- The builder returns source-linked segments in policy, required-source,
  conversation-history, optional-source order. Conflicting source identifiers
  fail closed; identical records merge without weakening required status.

No correctness issue remains within this bounded library. `ContextPrincipal`
must be constructed by trusted application code from authenticated identity and
current project membership. This module is not integrated with a public API,
does not provide distributed storage, and does not implement source correction,
deletion, retention policy or production encryption. Phase 4 is not complete.

## Verification

`tests/test_context_store.py` and `tests/test_context_preparation.py`: 19 passed.
The store tests cover project/user/tenant boundaries, immutable revisions,
unauthorized-source non-materialization, trusted policy assembly, revoked
membership, restart persistence, concurrent appends and checksum failures.
Full offline suite: 386 passed, 8 integration tests deselected. Ruff passed,
Mypy passed across 105 source files, compileall passed and `git diff --check`
passed. No external integrations, live services or GPU certification ran.
