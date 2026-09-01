# vLLM Compatibility Matrix

**Research date:** August 31, 2026
**Spike pin:** `vllm==0.26.0`
**Production status:** not approved; Linux/NVIDIA run pending

| Area | 0.26.0 evidence | Ryuk E1 decision |
| --- | --- | --- |
| Native generation | `AsyncLLM.generate` async iterator | Worker adapter target |
| Cancellation | `AsyncLLM.abort(request_id)` | Must pass real-worker termination test |
| Streaming | async incremental outputs | Worker owns assembly; public streaming deferred |
| Priority | `priority` argument plus scheduler policy | Capability/config gated |
| LoRA | `lora_request`, add/remove APIs | Disabled initially |
| Multimodal | prompt variants/model-specific support | Unknown until artifact test |
| Admission | `check_admission` in current API | Normalize to Ryuk capacity failures |
| Tracing | `trace_headers` | Translate W3C context in worker |
| Metrics | Prometheus support and per-request metrics | Feed D2; never infer request success |
| Tokenization/templates | engine/model tokenizer configuration | Worker-owned and provenance-recorded |
| macOS controller | full CUDA execution is Linux-oriented | No vLLM/CUDA controller dependency |

## Kimi Matrix

| Artifact | Documentation evidence | Decision |
| --- | --- | --- |
| `moonshotai/Kimi-K2-Instruct` | Kimi-K2 tool parser documented in earlier vLLM releases | Candidate only; revalidate on 0.26.0 |
| `moonshotai/Kimi-K2.5` | Listed in vLLM 0.16 supported-model documentation | Candidate; multimodal contract not validated |
| Kimi K2.6 / later variants | Current docs contain platform-specific recommendations | No generic NVIDIA claim without exact artifact test |
| User-selected full/quantized Kimi artifact | Not yet specified | Blocking production benchmark and GO decision |

Model-family documentation is not deployment proof. Exact revision,
quantization, tokenizer/template, parallel layout, GPU memory, and remote-code
requirements must be captured by the spike result.

## Required Benchmark Workload

Record image digest, package versions, artifact revision, quantization, template,
GPU/interconnect/driver/CUDA, parallel configuration, concurrency, warmup, sample
count, input/output token distributions, TTFT, inter-token latency, end-to-end
latency, throughput, error rate, GPU memory/utilization, and estimated cost.

Required cases: concurrency 1/8/32; short 512/128 tokens; long 8K/512 tokens;
deadline cancellation; overload/admission; malformed request; worker restart;
and output comparison against the SGLang semantic fixtures.
