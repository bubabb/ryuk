# Ryuk

Ryuk is an early-stage, vendor-independent AI inference control plane. Its goal
is to select an appropriate model deployment, execute requests through
replaceable inference systems, record what happened, and eventually audit and
evaluate the result.

Ryuk is currently a prototype. It is not production-ready and must not be used
as though its mock output were real model inference.

## Current Capabilities

The implemented flow is:

```text
FastAPI request
  -> Ryuk InferenceRequest
  -> InferenceRouter
  -> preferred engine availability check
  -> fallback engine selection
  -> normalized InferenceResponse
```

The repository currently provides:

- A Ryuk-owned inference request, response, and engine contract
- An engine registry
- Availability-based preferred-engine fallback
- An async, bounded SGLang adapter using its native `/generate` interface
- A deterministic development mock engine
- Typed failures, deadlines, attempts, capability constraints, and cached runtime state
- Health, engine-status, and generation HTTP endpoints

The Ryuk-native vLLM controller adapter and isolated Linux/NVIDIA worker are
implemented, but their real-GPU contract and benchmark gates have not run in
this workspace. Dynamo has a deployment-level adapter and a measured adoption
gate; NVIDIA NIM has a pinned deployment adapter and opt-in contract suite.
TensorRT-LLM remains deliberately held behind its benchmark decision gate.

## Architecture Boundary

External inference systems remain behind Ryuk-owned adapters:

```text
InferenceRequest -> InferenceEngine -> InferenceResponse
```

Vendor SDK and API types must not become Ryuk's core domain model. Model,
engine, serving runtime, deployment, and compute are separate concepts in the
target architecture.

See [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) for the detailed review and
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the staged roadmap.

## Development Setup

The documented development environment uses Python 3.12 and the Conda
environment `ryuk-ai`.

```bash
conda activate ryuk-ai
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Review `.env` before starting the service. It is intentionally ignored by Git.
Never place real credentials in `.env.example`.

## Run the API

```bash
conda activate ryuk-ai
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `GET /health`
- `GET /inference/engines`
- `POST /inference/generate`
- `POST /v1/inference/chat`

Example development request:

```bash
curl http://127.0.0.1:8000/inference/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Explain what Ryuk is.",
    "model": "test-model",
    "preferred_engine": "sglang"
  }'
```

On a Mac without a local SGLang worker, SGLang being unavailable is expected.
With the development mock enabled, the router should fall back to mock.

## Validation

```bash
python -m compileall -q backend tests
python -m pytest -q
ruff check backend tests
mypy backend tests
```

## Project Status and Next Milestone

Stages through G3 are implemented. Production approval for vLLM, Dynamo, and
NIM remains blocked until their opt-in GPU/licensed contract and benchmark gates
pass against exact model revisions and immutable image digests. ADR-006 prevents
Ryuk and Dynamo from both routing workers. TensorRT-LLM is a documented HOLD
until a comparable benchmark demonstrates a workload-specific advantage.

Stages H through J now provide advanced task semantics, deterministic and
model-audit contracts, bounded evaluation policy, and reference production
control-plane primitives. External GPU validation and distributed production
operations remain explicit deployment gates; see ADR-007 and ADR-008.

Do not infer implemented behavior from roadmap documents. The code and passing
tests are authoritative.
