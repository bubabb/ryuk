# Model allocation pilot v1 — preregistered protocol

Date: 2026-09-24. User approved the proposed 26-task pilot.
Repository baseline: 32adfd1. Freeze the manifest hash before any scored response.

26 synthetic, bounded tasks: eight Luna/medium support tasks; twelve Sol scoped
implementation tasks (medium/high as recorded); six Astra/high architecture
reviews. This deliberate stratification is not a production workload distribution.
Report each stratum separately; do not interpret the aggregate as a randomized
estimate of all open-ticket performance. There is no all-Astra comparison arm.

No candidates see expected answers, hidden assertions or review rubrics. Each
receives only its prompt in a fresh temporary directory and returns a structured
content string. Tools, repository reads, web and delegation are forbidden by the
task protocol. CLI sandbox is read-only; it is not a hermetic confidentiality
boundary. A recorded tool call invalidates first-pass success. This is a bounded
reasoning/code-generation pilot, not a test of autonomous multi-file agent work.
The CLI still adds system context; record its full reported usage.

Prompts and checks are new synthetic tasks inspired by Ryuk invariants. We cannot
prove absence from model pretraining. They are held out from these candidate
sessions, not a claim of independently curated benchmark quality. The authoring
agent grades outputs it did not generate; this is a separate reviewer but not
an independent external human audit. No paid model judge is needed for this pilot.

P01–08: exact JSON object comparison. P09–20: compile and hidden behavioral
assertions, plus reviewer inspection for hardcoding, missing requirements or
unsafe behavior. Candidate code must be reviewed before any execution; use only
an isolated local process with a timeout and no live credentials/services.
P21–26: reviewer applies every listed criterion; no keyword-only grading.

First pass succeeds only if all criteria pass without correction. A tool-use
violation, incorrect output, or material reviewer correction is a failure.
Critical security/tenant/replay failures prevent aggregate acceptance even if
23 tasks pass. Infrastructure errors count as unrun, never model success, and
make the pilot incomplete. Do not retry failures to improve first-pass scores.

Provisional observed-rate gate: at least 23/26 first-pass successes and zero
critical failures, with all 26 responses graded. 23/26 = 88.46%. Also report a
95% Wilson interval; the lower bound must exceed 0.87 before making a stronger
population-rate claim, and even then sampling limitations remain. The pilot
cannot establish 87% per-model reliability with these small strata.

Record prompt/manifest hashes, repository baseline, requested model/effort,
CLI version, elapsed time, available token counters, and missing telemetry as
unknown. Requested model is not independently verified server identity. Include
probe/setup/review overhead separately if available; never call missing overhead
zero. Do not claim dollar savings from this run without matched baseline usage
and the account's applicable billing terms.

Connectivity-only probe (not scored): gpt-6-luna/low returned RYUK_PILOT_READY.
CLI usage: input 13,889, cached input 11,008, output 10, reasoning output 0.
Initial outer-sandbox initialization failed with read-only filesystem; approved
rerun outside that sandbox succeeded, with generated commands still read-only.
After P21's transient CLI failure, a separate gpt-6-astra/high connectivity probe
returned RYUK_ASTRA_READY: input 14,516, cached input 12,160, output 9,
reasoning output 0. The scored P21 response was not retried. No Ryuk provider
endpoint or infrastructure was contacted.

Pilot v1 outcome (2026-09-25): 23 passes, 1 critical failure (P20), 1 invalid
benchmark item (P02), and 1 unrun quality result due to P21 infrastructure
failure. The 23/24 valid-item observed rate is 95.83%; Wilson 95% interval
79.76–99.26%. The run is incomplete and the quality gate fails due to the
critical failure, so the requested 87% target remains unverified. Per-model:
Luna 7/7 valid items (P02 invalid); Sol 11/12 (P20 failed); Astra 5/5 (P21
unrun). These purposive samples are too small to support population claims.

Recorded usage for successful CLI turns (P01–20 excluding no output, P22–26):
Luna 112,240 input / 39,168 cached input / 366 output / 56 reasoning output;
Sol 170,994 / 47,104 / 6,688 / 4,578; Astra 73,354 / 0 / 1,895 / 351.
Failed P21 consumption is unknown. Setup probes, evaluator/grader calls, prior
conversation use and reviewer time are not part of these candidate totals.
Do not infer billing or savings from them. The ambiguous P02 item must be
rewritten with a typed field contract in a new preregistered pilot version;
include exact schema-version-row cardinality in future migration tasks.

Execution interface was checked against local codex-cli 0.156.1 help and
[official Codex developer commands](https://learn.chatgpt.com/docs/developer-commands).
Only the evaluation runner launches model requests; dry-run is the default.
