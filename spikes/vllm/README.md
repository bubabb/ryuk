# vLLM Linux/NVIDIA Spike

This directory is deliberately isolated from `backend/`. Run it only in a
Linux/NVIDIA environment with the pinned vLLM worker image or environment.

```bash
python spikes/vllm/preflight.py
python spikes/vllm/async_llm_spike.py \
  --model <exact-artifact-revision> \
  --tensor-parallel-size <gpu-count> \
  --output /tmp/ryuk-vllm-spike.json
```

The spike performs warmup and measured native `AsyncLLM` requests and writes
environment/provenance plus latency and throughput samples. Copy reviewed,
secret-free results into `spikes/vllm/results/`; do not commit model tokens,
hostnames, or credentials.

The checked-in macOS preflight is not an inference benchmark. E1 remains
production-blocked until a real result exists for the selected Kimi artifact.
