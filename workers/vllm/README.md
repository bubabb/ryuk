# Ryuk vLLM Worker

This Linux/NVIDIA process embeds native vLLM `AsyncLLM` and exposes only Ryuk's
private `/ryuk/v1` worker contract. It is not an OpenAI-compatible boundary.

Required configuration:

- `RYUK_VLLM_MODEL`: exact model artifact
- `RYUK_VLLM_MODEL_REVISION`: immutable revision for production
- `RYUK_VLLM_TENSOR_PARALLEL_SIZE`: visible GPU count used by tensor parallelism

Build the image from `workers/vllm/Dockerfile`, then pin the resulting digest in
deployment configuration. The base tag alone is not a production supply-chain
pin. Worker authentication and tenant isolation remain Stage J requirements;
deploy this endpoint only on a private authenticated service network meanwhile.

Set `VLLM_WORKER_TEST_BASE_URL` and run the integration marker to validate a real
worker. Run the E1 benchmark harness against the exact same image and artifact.
