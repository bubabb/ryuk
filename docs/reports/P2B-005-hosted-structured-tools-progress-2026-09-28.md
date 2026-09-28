# P2B-005 hosted structured-output and tool behavior — progress record

Date: 2026-09-28
Status: in progress; one DeepSeek tool-proposal contract verified

## Provider contract basis

Official NVIDIA material observed on 2026-09-28 advertises structured output and
function/tool calls for Kimi K3 and describes tool-capable structured API output
for DeepSeek V4.1 Flash. Kimi's endpoint reference explicitly exposes
OpenAI-compatible `tools`; DeepSeek's endpoint accepts an OpenAI
`ChatCompletionRequest`. The documentation does not remove the need for live
contract evidence:

- https://docs.api.nvidia.com/nim/re/reference/moonshotai-kimi-k3
- https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k3-infer
- https://docs.api.nvidia.com/nim/re/reference/nvidia-deepseek-v4_1-flash
- https://docs.api.nvidia.com/nim/reference/nvidia-deepseek-v4_1-flash-infer

## Bounded contract

`scripts/probe_nvidia_hosted_structured_tools.py` concurrently sent two requests
to each exact approved route, each with temperature zero, a 128-token output cap
and a 180-second timeout:

1. A `response_format: {"type": "json_object"}` request requiring exactly
   `{"status":"ready"}`.
2. One declared `lookup_status` function requiring exactly one proposal with
   arguments `{"item":"ryuk"}`.

No returned tool proposal was or could be executed by the probe. Retained
evidence contains only identity, timing, status, content/tool presence,
deterministic validation booleans and usage counts. It excludes credentials,
headers, prompt/output/reasoning text, tool arguments, call/response IDs and
error bodies.

## Results

The sanitized result is
`evidence/phase2b/p2b-005-hosted-structured-tools-2026-09-28.json`.

| Profile | Structured output | Tool proposal |
| --- | --- | --- |
| Kimi K3 | `ReadTimeout` at 180.141 s; unverified | `ReadTimeout` at 180.134 s; unverified |
| DeepSeek V4.1 Flash | HTTP 200 with exact identity and usage, but no content; unverified | HTTP 200 in 76.007 s; exact identity; exactly one requested call with valid JSON and exact arguments; supported at this tested point |

DeepSeek structured-output usage was 41 prompt, 11 completion and 52 total
tokens. Its tool-proposal usage was 306 prompt, 56 completion and 362 total
tokens. The tool proposal was not executed.

An HTTP 200 without schema-valid content is not treated as structured-output
support. A timeout is neither positive nor negative capability proof. The
DeepSeek tool result verifies proposal serialization only; it does not verify
tool execution, multi-turn tool-result continuation, preserved reasoning/tool
history, authority, safety or production eligibility.

## Review

The implementation review added regression cases proving that valid-looking
output cannot override a response-model mismatch and that extra/wrong tool
arguments fail the exact contract. Existing tests prove response content,
reasoning, tool arguments, IDs and provider error messages are not retained.
The four operations are bounded, concurrent and never retried automatically.

P2B-005 remains `IN PROGRESS`. Kimi structured/tool behavior and DeepSeek
structured output remain unverified. The deployment registry continues to
declare structured output unsupported, and no tool execution path was enabled.
