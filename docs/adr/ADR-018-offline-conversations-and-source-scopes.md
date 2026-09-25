# ADR-018: offline conversations and source-scoped context assembly

Date: 2026-09-25. Status: implemented for offline synthetic/public use only.
The store and builder are internal libraries; no public context API or
production persistence is enabled.

## Decision

Add a separate `SQLiteContextStore` for context conversations and source
records, rather than reusing the workflow database. A trusted
`ContextPrincipal` carries one tenant, one user, and the project memberships
resolved by the application authorization layer. The context package does not
accept tenant/project/user identity from message content or a context source.

Conversations are scoped to a project and either to their owner (`user`) or to
current project members (`project`). Private conversations remain readable by
their owner within the tenant. Project conversations require current project
membership. Creating a conversation or source requires project membership;
project context assembly also requires current membership, including when the
conversation itself is private.

Source content is kept separately from ordered conversation entries. Sources
are immutable at `(tenant, source_id, revision)` and include project, owner,
scope, role, declared origin/trust, creation time and SHA-256 content digest.
Reusing a revision is idempotent only when every saved attribute and content
match; changed content requires a new revision. Conversation messages are
source records linked through an ordered, foreign-key constrained entry. Adding
a message and its source/entry is one transaction.

An owner-private source cannot be attached to a project-visible conversation.
Any attached or selected source must belong to the conversation's project. An
owner-private conversation may refer to a project source only while its owner
retains access to that project. Project membership is checked at read time, not
only when a reference is created.

`ContextBuilder` receives server-owned policy segments keyed by tenant/project;
it fails when the policy is missing. It requires at least one required
objective/criteria source, authorizes the conversation, authorizes every source
reference, then reads source content. If any selected source is missing or
unauthorized, the entire build fails with a generic access error. It does not
silently omit inaccessible content and return a partial prompt. Recent messages
are selected only after conversation authorization and each selected source is
checked before content is loaded.

Built context is ordered as trusted system policy, required source records,
recent conversation messages in chronological order, then optional source
records. Duplicate source IDs merge only if revision, role, origin and content
match; required status is preserved and priority takes the greater value.
Conflicting IDs fail closed. The builder returns source-linked `ContextSegment`
records consumed by ADR-017's candidate-specific fitting function.

## Data and trust boundaries

Only `ContextTrust.POLICY` records configured by the server may occupy the
system role; policy must be required. Assistant role is limited to explicitly
typed assistant history. Other source text uses the user role. Trust/origin
labels describe declared provenance and do not grant authorization or certify
truth. The principal is an internal trust boundary: application code must
derive it from authenticated identity and current project membership. Passing
caller-controlled project IDs as `ContextPrincipal.project_ids` would violate
this ADR.

The SQLite store is a local offline reference. It uses transactions, WAL,
foreign keys, per-source checksums and an explicit schema version. It does not
provide distributed admission, encryption-at-rest policy, retention/deletion,
backup/restore certification, or a public API. No production data is approved.
Source correction/deletion invalidation and context snapshot retention are
deferred to CTX-004.

## Verification and limits

`tests/test_context_store.py` exercises private/project access, tenant and
membership boundaries, immutable revisions, same-project source restrictions,
authorization before source-content materialization, policy-required assembly,
recent-message ordering, restart persistence, concurrent appends, and checksum
verification. `tests/test_context_preparation.py` continues to cover downstream
fitting. These are local synthetic tests, not a real identity-provider or
distributed-database integration. CTX-003 must bind verified tokenizer/template
profiles to actual dispatch; CTX-004 must add correction, deletion, retention,
compaction and two-candidate context evaluation before the Phase 4 exit gate.
