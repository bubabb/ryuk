# Phase 0 Baseline Verification Report

- Date: 2026-09-01
- Repository: `/home/sudosu/projects/ryuk`
- Branch: `main`
- Commit: `04a113884bedacaeb7d4d0a19538c387736fc6b4`
- Commit subject: `Add model capability shortlist`
- Host: Linux x86_64, kernel `7.0.0-30-generic`
- Supported environment used: Conda `ryuk-ai`, Python 3.12.14
- Evidence status: Implemented and locally verified; no external deployment was
  integration-tested in this run.

The initial worktree was clean except for the untracked, user-provided
`RYUK_ARCHITECTURE_DESIGN.md` and `RYUK_DEVELOPMENT_PHASE_PLAN.md`. They were not
modified. `llms.md` was not read or changed.

## Baseline command evidence

The named environment existed but initially lacked the pinned development
dependencies. `requirements-dev.txt` was installed into that environment before
validation.

```text
python -m compileall -q backend tests                         PASS
python -m pytest -q                                          PASS
ruff check backend tests                                     PASS
mypy backend tests                                           PASS
```

The pre-change test result was:

```text
163 passed, 4 skipped, 1 warning in 1.16s
```

After the first Phase 1 vertical slice, the result is:

```text
171 passed, 4 skipped, 1 warning in 3.19s
Ruff: passed
Mypy: passed across 69 backend/test files
compileall: passed
```

After completing the remaining Phase 1 work:

```text
180 passed, 4 skipped, 1 warning in 3.80s
Ruff: passed
Mypy: passed across 73 backend/test/script files
compileall: passed
```

The four skips are external integration gates:

1. Dynamo: base URL, model, and version are not configured.
2. NIM: base URL, model, release, and profile are not configured.
3. SGLang: real-server base URL is not configured.
4. vLLM: GPU-worker base URL is not configured.

The warning is the already documented FastAPI/Starlette `TestClient` migration
warning. In the restricted command sandbox, TestClient cannot create a stream
file descriptor and hangs. The complete suite passes outside that sandbox; this
is an execution-environment limitation, not a Ryuk test failure.

Historical statements in `ARCHITECTURE_REVIEW.md` that no tests exist and that
mock containment, runtime collection, typed failures, or generation failover are
absent are obsolete for this commit. Current code and this baseline supersede
those historical implementation observations.

## Public API enforcement matrix

| Route | Class | Authentication | Role | Admission | Terminal record |
| --- | --- | --- | --- | --- | --- |
| `GET /health` | Health | Explicitly public | None | None | None |
| `GET /inference/engines` | Deployment status | Bearer API key | Operator/admin | Request and concurrency | Sanitized success/failure record |
| `POST /inference/generate` | Inference | Bearer API key | Inference/admin | Request, concurrency, estimated output tokens | Sanitized success/failure record |
| `POST /v1/inference/chat` | Inference | Bearer API key | Inference/admin | Request, concurrency, estimated output tokens | Sanitized success/failure record |
| `POST /v1/audit/validate` | Audit/evaluation | Bearer API key | Operator/admin | Request, concurrency, estimated input tokens | Sanitized success/failure record |

Identity is derived from the server-held API-key record. None of these request
schemas accepts a tenant or role field. Missing, malformed, unknown, expired,
and revoked credentials fail with a safe 401; insufficient roles fail with 403;
quota rejection fails with 429 before the inference router is contacted.

The current application default contains no keys or quota policies and therefore
fails closed. A server-owned JSON configuration can load hashed key records and
quota policies, and production configuration requires both that file and a
durable record path. Production resolves supported secret references only at the
adapter boundary and verifies observed identity for production-eligible
deployments before accepting traffic.

## Deployment and capability evidence inventory

| Boundary | Current evidence | External gate |
| --- | --- | --- |
| Development mock | Implemented and locally tested; synthetic, never production eligible | Not applicable |
| SGLang native HTTP adapter | Implemented with simulated contract/failure tests; default deployment has text capability configured | Real server test skipped; model identity and production eligibility unknown |
| vLLM Ryuk-native worker | Implemented with controller/worker unit contracts | Real Linux/NVIDIA GPU worker test skipped |
| NVIDIA Dynamo frontend | Implemented behind ADR-006 hold and benchmark gate | Real deployment test skipped; production adoption not approved |
| NVIDIA NIM managed adapter | Implemented with pinned release/profile requirements and simulated contracts | Licensed real deployment test skipped |
| TensorRT-LLM | Deliberate HOLD; no approved executable adapter | Comparable benchmark evidence absent |

No adapter in this run is Integration-tested, Benchmark-evaluated, or
Production-certified. Unconfigured capability claims remain Unknown.

## ADR and requirement traceability

| Source | Current modules | Principal tests/evidence |
| --- | --- | --- |
| ADR-001 vLLM worker boundary | `backend/inference/engines/vllm.py`, `vllm_worker.py`, `workers/vllm/` | `test_vllm_worker_adapter.py`, opt-in integration test |
| ADR-002 identity/provenance | `deployment.py`, `base.py`, registry and adapters | identity, deployment, API provenance tests |
| ADR-003 typed task/result | `contracts.py`, `advanced.py`, `compat.py` | contract, compatibility, advanced-contract tests |
| ADR-004 deadlines/attempts/failover | `router.py`, `errors.py`, adapters | execution, router, and failure tests |
| ADR-005 capability evidence | `capabilities.py`, `policy.py`, `runtime.py` | capability, policy, runtime tests |
| ADR-006 Dynamo boundary | `engines/dynamo.py`, registry | Dynamo unit test, opt-in integration, serving evaluation |
| ADR-007 production control plane | `backend/control/`, governed API dependencies in `main.py` | control-plane and API negative-path tests |
| ADR-008 audit/evaluation boundary | `backend/audit/`, `backend/evaluation/` | audit and evaluation tests/reports |
| Architecture design sections 3, 4, 13 | API control dependency, deployment router, redacted record payload | this report and API/control-plane tests |
| Development plan Phase 0 | repository/tool capture, matrices, traceability, issue list | this report |
| Development plan Phase 1 first slice | shared authentication, authorization, admission, one recorded inference route | API/control-plane tests |

## Prioritized confirmed gaps

| Priority | Gap | Owner | Containment |
| --- | --- | --- | --- |
| P1 | Add external secret-manager providers beyond the implemented environment reference | Unassigned | Production rejects inline credentials and unsupported providers |
| P1 | Certify two exact real deployments | Unassigned | All external capabilities retain non-production evidence labels |
| P1 | Resolve TestClient's announced `httpx2` migration | Unassigned | Current pinned suite passes with one warning |

## Document disposition

The two proposed Ryuk design documents are retained at repository root and are
included in the reviewed Git save at the project owner's request. Their
`Proposed` status remains explicit; tracking them does not represent completed
production behavior. The tracked, owner-controlled `llms.md` was not changed.

## Phase gate assessment

The repository baseline is green. Phase 0 evidence is recorded, with the four
external skips explicitly classified. Phase 1 is implemented for the current
public API surface: every non-health route is authenticated, role-authorized,
admitted, terminally recorded, and instrumented with redacted lifecycle events.
Production startup requires durable/configured control state, prohibits mock and
inline provider credentials, and verifies every production-eligible deployment's
observed identity. No streaming endpoint currently exists, so disconnected-stream
permit behavior remains attached to the future streaming vertical slice.
