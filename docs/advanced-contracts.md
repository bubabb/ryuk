# Advanced Task Contract Semantics

- Streaming is an ordered `start`, `delta`, `end` sequence. Cooperative
  cancellation must reach the selected adapter.
- Structured output uses a bounded JSON-schema subset and deterministic
  validation. Invalid output is never silently repaired.
- Tool calls contain a name and validated arguments. Ryuk represents them but
  does not execute them.
- The first multimodal slice accepts at most eight JPEG, PNG, or WebP HTTPS
  object references. A separate allowlisted fetcher is required to prevent SSRF.
- Embedding and reranking are separate task/result families and cannot fall back
  to a generation-only deployment.

Unknown capability evidence makes a deployment ineligible; the router does not
emulate missing features.
