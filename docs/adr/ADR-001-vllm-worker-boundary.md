# ADR-001: vLLM Worker Boundary

- **Status:** Accepted for E2 implementation; production approval conditional
- **Date:** August 31, 2026
- **Research target:** vLLM `0.26.0`
- **Related milestone:** E1

## Decision

Ryuk will integrate vLLM through a dedicated Linux/NVIDIA worker owned by Ryuk.
The worker will embed vLLM's native `AsyncLLM` API and expose a small,
versioned, Ryuk-owned RPC contract. The macOS control plane will not install or
import vLLM, PyTorch, CUDA, Hugging Face tokenizers, or vLLM protocol types.

The initial spike is pinned to vLLM `0.26.0`; image tags and Python dependencies
must additionally be locked by digest/hash before production. This pin is a
validation target, not a claim that Kimi production serving has passed.

## Why `AsyncLLM`

The native engine provides async generation, streaming output, request IDs,
priority, trace headers, LoRA requests, admission checks, and explicit abort.
That is a better semantic boundary than translating Ryuk into vLLM's
OpenAI-compatible server. The worker owns conversion from Ryuk task messages to
model prompts/tokens and conversion from vLLM outputs to Ryuk results.

The vLLM OpenAI server is rejected as Ryuk's internal protocol because it would
make an optional compatibility schema foundational. It remains useful for
operator diagnostics and upstream benchmark tooling. Dynamo-managed vLLM is
deferred to ADR-006: adding Dynamo changes scheduling, discovery, and failure
ownership and must not be disguised as the same topology.

## Ownership

- Ryuk controller: task semantics, hard constraints, routing, deadlines,
  attempts, audit, and public API.
- Ryuk vLLM worker: vLLM lifecycle, tokenization, model chat template, sampling
  translation, streaming assembly, abort, engine metrics, and exact model/runtime
  identity.
- Deployment configuration: artifact revision, tokenizer revision, template
  policy, tensor/pipeline parallelism, quantization, dtype, CUDA image digest,
  GPU topology, and trust-remote-code decision.

The controller sends typed chat messages, not a preformatted model prompt. This
keeps model-specific templates next to the tokenizer/model revision. The worker
must return the template/tokenizer provenance used.

## Feature Gate

Text generation, streaming groundwork, cancellation, priority, LoRA, and
multimodal inputs are technically exposed by current vLLM APIs, but each remains
a deployment capability. E2 starts with non-streaming text/chat only. Structured
output, tools, LoRA, and multimodality stay disabled until contract fixtures and
the chosen Kimi artifact validate them. Prometheus data is observational runtime
state, never transaction truth.

## Go/No-Go

**GO for E2 worker-boundary implementation and a Linux/NVIDIA validation run.**

**NO-GO for production or truthful Kimi capability claims** until all of these
are recorded: exact Kimi artifact/revision and license, immutable vLLM image
digest, driver/CUDA/GPU topology, successful load and identity evidence,
cancellation behavior, semantic contract results, and benchmark baselines under
the workload matrix. The local Mac preflight found no NVIDIA runtime and no vLLM
installation, which is the intended controller isolation—not a GPU benchmark.

## Primary Sources

- [vLLM 0.26.0 release](https://github.com/vllm-project/vllm/releases/tag/v0.26.0)
- [AsyncLLM API](https://docs.vllm.ai/en/latest/api/vllm/v1/engine/async_llm/)
- [supported models](https://docs.vllm.ai/en/latest/models/supported_models/)
- [GPU installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)
- [production metrics](https://docs.vllm.ai/en/latest/usage/metrics/)
- [scheduler configuration](https://docs.vllm.ai/en/latest/api/vllm/config/scheduler/)
- [official AsyncLLM example](https://github.com/vllm-project/vllm/blob/main/examples/offline_inference/async_llm_streaming.py)
