# NVIDIA NIM LLM Deployment Profile

Ryuk's first NIM profile is standard-mode NIM LLM **2.0.11**, whose documented
backend is vLLM 0.27.0. This is an evaluation pin. A production deployment must
also pin an immutable container digest, model artifact/revision, NIM profile ID,
driver, GPU type/count, and data location.

The adapter uses the documented NIM surfaces:

- `/v1/health/live` and `/v1/health/ready` for lifecycle state;
- `/v1/version`, `/v1/metadata`, and `/v1/models` for provenance checks;
- `/v1/completions` and `/v1/chat/completions` for non-streaming inference;
- `/v1/metrics` as an operator scrape target, not a request-time dependency.

Although the product exposes an OpenAI-compatible inference surface, those
payloads exist only inside `NIMEngine`. Ryuk routes typed `InferenceTask` values
and receives typed `AdapterInferenceResult` values. NIM is never Ryuk's
universal protocol.

`NIM_RELEASE`, `NIM_PROFILE_ID`, and `NIM_MODEL_ARTIFACT_ID` are mandatory when
enabled. Identity inspection fails closed when the running release, profile, or
served model differs. Credentials are optional deployment configuration and
must never be stored in example files or provenance.

The opt-in contract suite uses `NIM_TEST_BASE_URL`, `NIM_TEST_MODEL`,
`NIM_TEST_RELEASE`, `NIM_TEST_PROFILE_ID`, and optionally `NIM_TEST_API_KEY`.
Licensing, registry access, and GPU operation remain operator responsibilities.

Sources: [NIM API reference](https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html),
[architecture](https://docs.nvidia.com/nim/large-language-models/latest/reference/architecture.html),
and [2.0.11 release notes](https://docs.nvidia.com/nim/large-language-models/latest/release-notes.html).
