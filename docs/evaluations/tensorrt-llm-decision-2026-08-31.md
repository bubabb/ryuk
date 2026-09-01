# TensorRT-LLM Decision Gate — 2026-08-31

## Decision: HOLD

TensorRT-LLM is not enabled and no adapter is implemented. This is intentional,
not an incomplete checklist item.

Current upstream documentation lists `moonshotai/Kimi-K2.5` support and Dynamo
1.4.1 pins TensorRT-LLM 1.3.0rc22. That establishes possible compatibility, not
a measurable advantage for Ryuk. This macOS/ARM controller has no NVIDIA GPU,
and no identical-hardware comparison against the existing vLLM worker or a
Dynamo deployment has been supplied.

## Required spike

Use a pinned Kimi-K2.5 artifact revision on one documented Hopper or Blackwell
topology. Compare TensorRT-LLM 1.3.0rc22 with the existing vLLM baseline using
the same image provenance, prompts, concurrency, input/output lengths, sampling,
and warm-up. Measure TTFT, inter-token latency, output throughput, failures,
recovery, peak memory, engine-build time, and operational complexity.

Place the two machine-readable `ServingBenchmark` records in a JSON report and
run:

```bash
python -m scripts.evaluate_serving_candidate path/to/report.json
```

Only an `adopt` result plus verified model output compatibility authorizes an
adapter milestone. A passing synthetic or cross-hardware comparison does not.

Sources: [TensorRT-LLM supported models](https://nvidia.github.io/TensorRT-LLM/latest/models/supported-models.html),
[quantization matrix](https://nvidia.github.io/TensorRT-LLM/latest/features/quantization.html),
and [Dynamo compatibility](https://docs.nvidia.com/dynamo/dev/reference/compatibility).
