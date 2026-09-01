Ryuk — Agent Instructions

Project Mission

Ryuk is an open, vendor-independent AI agent and inference orchestration platform.

Ryuk must be able to reason about a task, select an appropriate model and inference engine, execute the task, audit the result, evaluate its quality and accuracy, and retry or route elsewhere when necessary.

The long-term goal is not merely model inference. Ryuk should become an intelligent control layer over multiple models, inference engines, hardware environments, and AI providers.

⸻

Core Architectural Principle

Ryuk owns its internal interfaces.

Do not allow any external vendor, model provider, inference engine, SDK, or API protocol to become Ryuk’s internal abstraction.

The rest of Ryuk should not need to know whether an inference request was executed by:

* SGLang
* vLLM
* TensorRT-LLM
* NVIDIA Dynamo
* NVIDIA NIM
* another future inference engine
* a local model
* a remote model
* a proprietary provider used as an optional fallback

All external systems must be hidden behind Ryuk-owned interfaces.

The current primary abstraction is:

InferenceRequest -> InferenceEngine -> InferenceResponse

⸻

Vendor Independence

Vendor independence is a hard project requirement.

Do not architect Ryuk around:

* OpenAI APIs
* Anthropic APIs
* OpenAI Python SDK
* OpenAI-compatible API protocols
* a single NVIDIA inference technology
* a single cloud provider
* a single model family

OpenAI, Anthropic, or other proprietary providers may eventually exist as OPTIONAL fallback adapters.

They must never become foundational dependencies.

⸻

OpenAI-Compatible APIs

Do NOT use OpenAI-compatible APIs as Ryuk’s internal inference protocol.

For example, avoid making Ryuk depend on:

/v1/chat/completions

when a native engine interface is available.

Prefer native interfaces for each inference system.

Examples:

* SGLang: native SGLang generation interface
* vLLM: native vLLM engine / AsyncLLM interfaces where appropriate
* TensorRT-LLM: native TensorRT-LLM interfaces
* Dynamo: native NVIDIA Dynamo architecture/interfaces
* NIM: treat as its own adapter rather than Ryuk’s universal protocol

Adapters normalize the result into Ryuk’s own InferenceResponse.

⸻

Target Inference Engines

Ryuk is intended to support at least these inference systems:

1. SGLang
2. vLLM
3. TensorRT-LLM
4. NVIDIA Dynamo
5. NVIDIA NIM

These systems are NOT assumed to be equivalent.

Do not implement them as meaningless copies of one generic HTTP adapter.

Each adapter should respect the capabilities and architecture of the actual engine.

⸻

Intelligent Engine Selection

The final router should not simply use a fixed fallback order.

Ryuk should eventually rank candidate model/engine combinations using signals such as:

* task type
* expected accuracy
* historical accuracy
* model compatibility
* engine compatibility
* latency
* throughput
* context capacity
* GPU requirements
* hardware availability
* current engine health
* current load
* cost
* reliability
* task complexity
* structured-output requirements
* reasoning requirements

Early implementations may use simpler fallback behavior while this system is being built.

Do not confuse temporary fallback behavior with the final architecture.

⸻

Ryuk Intelligence Layers

Ryuk is intended to contain multiple intelligence functions.

Execution / Routing Intelligence

Determines how a user task should be executed.

Responsibilities will eventually include:

* classify the task
* identify requirements
* select model
* select inference engine
* select compute environment
* determine routing priorities
* execute the request

Audit Intelligence

Independently inspect generated output.

The auditor should look for issues such as:

* factual errors
* hallucinations
* unsupported claims
* missing information
* contradictions
* failure to follow the request
* unsafe assumptions
* reasoning defects
* malformed structured output

The auditor should not blindly trust the generator.

Evaluation Intelligence

Evaluate output quality and determine whether the result is acceptable.

Potential outcomes include:

* accept
* regenerate
* revise
* use another model
* use another inference engine
* perform additional verification
* escalate to another evaluator

Audit and evaluation should remain conceptually separate even if early implementations are simple.

⸻

Model Strategy

Ryuk should support multiple model families.

Kimi is currently an important target, particularly large/full variants deployed on NVIDIA infrastructure.

However, Ryuk must not become a Kimi-only system.

Future models may include open-weight and proprietary models.

Model choice and inference-engine choice are separate decisions.

⸻

NVIDIA Strategy

NVIDIA infrastructure is an important compute target.

Potential technologies include:

* NVIDIA GPUs
* NVIDIA cloud compute
* NVIDIA developer programs
* Dynamo
* TensorRT-LLM
* NIM
* SGLang on NVIDIA GPUs
* vLLM on NVIDIA GPUs

Do not assume development occurs on the same machine that performs inference.

The local Mac may function as:

* development machine
* controller
* API server
* routing/control plane

GPU inference may run remotely on Linux/NVIDIA infrastructure.

Keep control-plane and inference-worker concerns separable.

⸻

Current Development Environment

Repository:

/Users/bubagv/Desktop/projects/ryuk

Primary Python environment:

ryuk-ai

Known environment during initial development:

* Python 3.12.14
* Conda environment: ryuk-ai
* macOS development host

Typical activation:

conda activate ryuk-ai

⸻

Current Repository Areas

The repository has been designed around areas including:

* backend/
* frontend/
* cli/
* agent/
* infrastructure/
* tests/
* docs/

Inspect the actual repository before assuming any directory or file currently exists.

Never infer current implementation solely from this document.

The code is the authority for implementation state.

⸻

Current Backend Inference Architecture

The backend currently contains an inference abstraction under:

backend/inference/

Important files include:

* base.py
* registry.py
* router.py
* engines/

Current engine work includes:

* SGLang adapter
* development mock engine
* placeholders/future adapters for other engines

Inspect these files before modifying them.

⸻

Current Inference Contract

Ryuk currently defines its own concepts for:

* InferenceRequest
* InferenceResponse
* InferenceEngine

Maintain this abstraction unless there is a strong architectural reason to evolve it.

Do not replace it with a vendor SDK’s request/response objects.

Vendor-specific objects should remain inside adapters.

⸻

Current SGLang Behavior

SGLang is the first real inference adapter.

The development configuration currently points at approximately:

http://127.0.0.1:30000

The local Mac normally does not have the production SGLang/NVIDIA inference server running.

Therefore:

SGLang available = false

may be completely correct during local development.

Do not treat an offline local SGLang endpoint as a code failure without investigating.

⸻

Mock Engine

A mock inference engine exists for local development.

Its purpose is to test:

* engine registration
* engine availability
* router fallback
* FastAPI integration
* normalized responses
* end-to-end control flow

The mock engine is NOT a production inference backend.

Do not accidentally treat mock output as real model inference.

The mock engine should eventually be disabled outside development/test environments.

⸻

Current Proven Flow

The following control flow has already been tested successfully:

User/API request

-> FastAPI

-> Ryuk InferenceRouter

-> preferred SGLang backend

-> SGLang unavailable

-> fallback engine search

-> mock engine available

-> mock generation

-> normalized InferenceResponse

-> FastAPI response

Preserve this behavior while extending the architecture.

⸻

Current API

The FastAPI backend includes a health endpoint similar to:

GET /health

The inference control plane includes an engine-status endpoint similar to:

GET /inference/engines

Generation currently uses an endpoint similar to:

POST /inference/generate

Inspect backend/main.py for the actual current implementation before editing.

⸻

Configuration

Application configuration lives in:

backend/config.py

Configuration uses pydantic-settings.

Inference-engine availability should be configuration-driven.

Examples of expected settings include concepts similar to:

* sglang_enabled
* sglang_base_url
* vllm_enabled
* vllm_base_url
* tensorrt_llm_enabled
* tensorrt_llm_base_url
* dynamo_enabled
* dynamo_base_url
* nim_enabled
* nim_base_url
* mock_enabled

Inspect actual configuration before adding duplicate settings.

⸻

Secrets

Never commit secrets.

Examples include:

* API keys
* NVIDIA credentials
* model-provider credentials
* Supabase service-role keys
* database passwords
* tokens
* private certificates

Do not print secrets into logs or tests.

Treat .env as local/private unless the repository explicitly demonstrates otherwise.

Use .env.example for documented placeholder configuration.

⸻

Coding Principles

Prefer:

* explicit interfaces
* typed Python
* small focused modules
* async interfaces where network or inference work is asynchronous
* dependency boundaries
* testable components
* configuration over hard-coded deployment values
* descriptive errors
* graceful engine failure
* normalized responses
* observability

Avoid:

* unnecessary frameworks
* premature complexity
* duplicated abstractions
* vendor-specific types leaking into core code
* giant modules
* silent exception swallowing
* hard-coded credentials
* fake production implementations
* claiming an adapter works when it has only been syntactically created

⸻

Engine Failure Philosophy

An unavailable inference engine should not crash Ryuk.

The router should be able to:

1. identify availability
2. skip unavailable candidates
3. select an appropriate alternative
4. return a controlled failure if no valid engine exists

Eventually health, performance, and reliability information should inform routing decisions.

Health checks should have strict timeouts.

One unavailable engine must not freeze the overall application.

⸻

Development Safety

Before editing:

1. inspect relevant existing files
2. inspect Git status
3. understand the current abstraction
4. avoid overwriting working code unnecessarily

After editing:

1. compile relevant Python files
2. run relevant tests
3. inspect failures
4. fix regressions
5. inspect Git diff
6. verify no secrets or unwanted generated files were added

Do not report success merely because code was written.

Validate it.

⸻

Minimum Python Validation

For affected Python modules, use appropriate validation such as:

python -m py_compile <files>

When tests exist, run the relevant tests.

For broader changes, run the complete test suite when reasonably practical.

⸻

FastAPI Development

When testing the API, a normal local command is:

uvicorn backend.main:app --host 127.0.0.1 --port 8000

--reload may be useful during development but has previously caused a stuck development process after file changes.

If the API unexpectedly hangs:

* test /health
* inspect the Uvicorn process
* inspect port 8000
* restart without --reload
* distinguish server-process problems from inference-engine health problems

Do not immediately rewrite working inference code when the server process itself is stale.

⸻

Git Behavior

Before making changes, inspect:

git status

Do not destroy or overwrite unrelated user changes.

Do not reset, discard, or rewrite existing work unless explicitly instructed.

Before committing, inspect:

git diff

Never commit:

* .env
* credentials
* caches
* temporary files
* local secrets

Use meaningful commit messages.

Do not rewrite existing history unless explicitly requested.

⸻

Research Requirements

Inference technologies evolve quickly.

Before implementing or materially changing integration with:

* SGLang
* vLLM
* TensorRT-LLM
* Dynamo
* NIM
* NVIDIA cloud infrastructure
* Kimi model deployment

verify the current official documentation.

Prefer:

1. official project documentation
2. official GitHub repositories
3. NVIDIA documentation where relevant
4. model-publisher documentation

Do not rely on stale assumptions about APIs.

⸻

Architecture Before Convenience

Do not choose an integration merely because it is easiest to demonstrate.

In particular:

* do not adopt an OpenAI-compatible server simply because an SDK already supports it
* do not force all inference engines into identical deployment models
* do not confuse an HTTP endpoint with the underlying inference architecture
* do not make temporary local-development limitations permanent architectural decisions

Preserve Ryuk’s ability to evolve.

⸻

Near-Term Development Direction

The current direction is:

1. preserve the existing inference abstraction
2. strengthen engine capability metadata
3. model differences between inference engines
4. implement a real vLLM adapter
5. implement TensorRT-LLM support
6. implement Dynamo support
7. implement NIM support
8. improve routing beyond fixed fallback order
9. add model registry/capability awareness
10. add audit intelligence
11. add evaluation intelligence
12. connect to remote NVIDIA compute
13. evaluate Kimi deployment on that infrastructure

Do not assume this order is immutable if repository state or technical evidence suggests a better dependency order.

⸻

Agent Working Style

When working on Ryuk:

* inspect before editing
* make incremental changes
* preserve working milestones
* explain important architectural deviations
* test what you change
* distinguish prototype behavior from production behavior
* do not fabricate successful integrations
* do not replace deliberate architecture with vendor convenience

When uncertain about an architectural decision with long-term consequences, prefer preserving abstraction boundaries.

The primary objective is not merely to make code execute.

The objective is to build Ryuk into a robust, intelligent, auditable, multi-model and multi-engine AI orchestration system.

Current Development Checkpoint — Resume Here

This section records the exact development checkpoint reached before work moved to Codex CLI.

Last Known Working State

The local development environment was:

/Users/bubagv/Desktop/projects/ryuk

Conda environment:

ryuk-ai

Python:

3.12.14

Git branch:

main

At the last checkpoint, git status reported:

nothing to commit, working tree clean

The branch was up to date with origin/main.

Before making new changes, verify this is still true rather than assuming it.

⸻

What Has Been Built

The initial inference abstraction has been implemented.

Relevant structure includes approximately:

backend/inference/base.py

backend/inference/registry.py

backend/inference/router.py

backend/inference/engines/

Engine files include work/placeholders for:

* SGLang
* vLLM
* TensorRT-LLM
* Dynamo
* NIM
* mock development engine

Inspect the actual files before making changes.

⸻

Inference Base Contract

Ryuk owns its inference abstraction.

The current implementation defines concepts equivalent to:

InferenceRequest

InferenceResponse

InferenceEngine

InferenceEngine provides the common contract that inference backends implement.

The rest of Ryuk should operate against this contract rather than vendor-specific request/response types.

⸻

Engine Registry

EngineRegistry has been implemented.

It supports registering and retrieving inference engines.

A configuration-driven registry builder has also been introduced.

At the last checkpoint, the development registry successfully contained:

sglang

and:

mock

The observed API result was:

count = 2

with:

sglang -> available = false

mock -> available = true

This was expected.

⸻

Inference Router

The initial InferenceRouter has been implemented.

The current router supports:

* selecting a preferred engine
* checking whether that engine is available
* skipping an unavailable preferred engine
* searching registered fallback engines
* selecting an available fallback
* returning a controlled error when no engine is available

This is intentionally an EARLY router.

It currently performs availability/fallback routing.

It is NOT yet the final intelligent routing system.

Do not mistake registration/fallback order for the intended long-term engine-selection algorithm.

⸻

SGLang Adapter

A real SGLang adapter has been started.

The design deliberately uses SGLang’s native interface rather than making Ryuk depend on OpenAI-compatible /v1/chat/completions.

During local Mac development, the configured SGLang endpoint was:

http://127.0.0.1:30000

No SGLang NVIDIA inference worker was running locally.

Therefore:

sglang -> available = false

was the expected result.

This does not indicate that the adapter is broken.

The actual production SGLang worker is expected to run later on Linux/NVIDIA infrastructure.

⸻

Mock Engine

A mock development engine was added at:

backend/inference/engines/mock.py

It reports itself as available and produces deterministic fake inference output.

It exists only to verify Ryuk’s orchestration path without requiring GPU infrastructure.

It must not become a production inference backend.

⸻

FastAPI Integration

The inference layer has been connected to FastAPI.

The following paths were tested:

GET /health

GET /inference/engines

POST /inference/generate

The health endpoint successfully returned a response equivalent to:

status = ok

service = Ryuk AI

environment = development

The engine endpoint successfully returned approximately:

sglang -> offline

mock -> available

⸻

Proven End-to-End Fallback Test

The most important successful test before this checkpoint was an actual FastAPI inference request.

The request preferred:

sglang

SGLang was unavailable.

Ryuk then automatically selected:

mock

The request completed successfully.

The observed response contained approximately:

text = "Mock response for: Explain what Ryuk is."

model = "test-model"

engine = "mock"

latency_ms = 1.0

metadata.mock = true

This proves the following path works:

FastAPI request

-> Ryuk InferenceRequest

-> InferenceRouter

-> preferred SGLang engine

-> SGLang health check fails

-> router searches fallback engines

-> mock engine selected

-> mock generates result

-> result normalized into InferenceResponse

-> FastAPI returns response

Preserve this behavior while extending the system.

⸻

Development Server Issue Already Encountered

During testing, a Uvicorn process running with:

--reload

became stuck.

Symptoms included both:

GET /inference/engines

and eventually:

GET /health

hanging.

The problem was resolved by stopping the stale Uvicorn process and restarting the server without --reload:

uvicorn backend.main:app --host 127.0.0.1 --port 8000

After restarting, /health returned immediately.

/inference/engines also returned correctly.

Do not assume a future API hang is caused by SGLang or routing logic before checking the development server process.

Health checks should eventually be hardened further so an unavailable engine cannot make the control plane unresponsive.

⸻

Exact Point Where Development Stopped

Development stopped immediately before implementing the next real inference engine.

The next engine under consideration was:

vLLM

Before writing the vLLM adapter, an architectural issue was identified.

Ryuk should NOT simply copy the SGLang HTTP adapter pattern and make every inference engine look like:

Ryuk -> HTTP -> generic /generate endpoint

The different inference engines have materially different architectures and capabilities.

For vLLM specifically, the plan was to investigate and use its native engine interfaces where appropriate rather than defaulting to its OpenAI-compatible server.

The relevant native vLLM architecture under consideration included concepts such as:

AsyncLLM

or the appropriate current native asynchronous vLLM engine interface.

Current official vLLM documentation MUST be checked before implementation because its APIs evolve.

Do not implement against remembered or stale API names without verification.

⸻

What We Were Going To Build Next

The immediate next task was changed from:

“implement vllm.py immediately”

to:

build Ryuk’s engine capability model first.

This is the recommended resume point.

The reason is important.

SGLang, vLLM, TensorRT-LLM, Dynamo, and NIM should not be represented as interchangeable engines that differ only by URL.

Ryuk eventually needs enough metadata to understand what each engine/model combination can actually do.

⸻

NEXT TASK — Engine Capability Model

Before implementing the full vLLM adapter, design and implement an engine capability representation owned by Ryuk.

The capability model should eventually be able to represent information such as:

* engine name
* engine type
* local vs remote execution
* supported model families
* supported hardware
* NVIDIA GPU requirements
* minimum/expected VRAM requirements where knowable
* tensor parallelism support
* pipeline parallelism support
* distributed inference support
* continuous batching support
* prefix caching support
* speculative decoding support
* quantization support
* structured output support
* streaming support
* maximum/known context constraints
* multimodal capability where applicable
* native asynchronous execution support
* production-serving suitability
* health
* load
* latency
* throughput
* estimated cost
* historical reliability
* historical output-quality metrics

Do not attempt to hard-code every possible capability in the first version.

Start with a clean extensible representation.

Keep static capabilities separate from dynamic runtime metrics where practical.

For example:

Static-ish information:

EngineCapabilities

Dynamic information:

EngineRuntimeState

or equivalent concepts.

The exact names may change if a better design emerges.

⸻

Why Capability Modeling Comes Before More Adapters

The current router effectively asks:

“Which registered engine is available?”

The intended Ryuk router should eventually ask:

“Which model + inference engine + compute environment is best for THIS task under the current constraints?”

For example, future routing may resemble:

User task

-> Task classification

-> Determine requirements

-> Identify compatible models

-> Identify compatible inference engines

-> Identify available compute

-> Evaluate capability constraints

-> Score candidate combinations

-> Execute best candidate

-> Audit output

-> Evaluate output

-> Accept OR retry/re-route

This requires more information than a simple engine name and health boolean.

⸻

Router Evolution Target

Do not replace the current working fallback router all at once.

Evolve it incrementally.

A future candidate scoring system may consider dimensions such as:

compatibility_score

accuracy_score

latency_score

cost_score

reliability_score

availability_score

context_score

hardware_score

task_fit_score

The eventual score might conceptually resemble:

candidate_score = weighted combination of routing signals

However, do not lock Ryuk prematurely into a simplistic weighted-average formula.

Some requirements may be hard constraints rather than scores.

Example:

If a task requires a context size larger than a candidate can support, that candidate should be eliminated rather than merely receiving a lower score.

Similarly, if an engine cannot execute the selected model, it is not a valid candidate.

⸻

Model Selection and Engine Selection Must Remain Separate

Do not collapse:

model

and:

inference engine

into one concept.

Ryuk should eventually reason about combinations such as:

Kimi model + SGLang

Kimi model + vLLM

another model + TensorRT-LLM

where technically supported.

The model registry should describe model capabilities.

The engine registry should describe inference-engine capabilities.

The router should eventually evaluate valid combinations.

⸻

vLLM — Planned Work After Capability Foundation

Once the first engine-capability representation exists, continue with the vLLM adapter.

Before implementation:

1. inspect the current repository
2. inspect existing backend/inference/engines/vllm.py
3. check current official vLLM documentation
4. identify the correct native production-capable integration
5. avoid OpenAI-compatible APIs as Ryuk’s foundation
6. determine whether the adapter belongs in the controller process or an NVIDIA worker process
7. preserve the InferenceEngine abstraction
8. normalize native vLLM output into InferenceResponse
9. add health/availability behavior
10. test without requiring the Mac to pretend it has NVIDIA hardware

The Mac development environment should not require installing a heavy NVIDIA/vLLM runtime merely to import the Ryuk backend.

Use optional dependencies and deployment boundaries appropriately.

⸻

Planned Engine Order

After the capability foundation, the tentative implementation direction was:

1. capability model
2. vLLM
3. TensorRT-LLM
4. NVIDIA Dynamo
5. NVIDIA NIM

SGLang already has the first adapter.

This order is not sacred.

Change it if current technical evidence shows a better dependency sequence.

⸻

Important Future Architecture

The intended deployment direction is approximately:

Local/controller environment:

Ryuk API

Ryuk agent

task classifier

model selector

engine router

auditor

evaluator

control plane

↓

Remote Linux/NVIDIA compute

↓

SGLang / vLLM / TensorRT-LLM / Dynamo / NIM

↓

Kimi and other models

The controller and inference worker must not be assumed to be the same machine.

⸻

Longer-Term Routing Goal

Ryuk should ultimately have enough intelligence to decide:

* which model is most appropriate
* which inference engine is most appropriate
* which available hardware should run it
* whether the expected accuracy is sufficient
* whether another model should verify the result
* whether the answer needs external evidence
* whether latency or accuracy matters more for the task
* whether the output should be regenerated
* whether another engine/model combination should be attempted

This is the foundation for the larger Ryuk concept:

generation + routing + auditing + evaluation

rather than simply:

prompt -> model -> answer

⸻

Resume Procedure for the Next Coding Agent

When resuming work:

1. Change into the repository:

cd /Users/bubagv/Desktop/projects/ryuk

2. Activate the environment if needed:

conda activate ryuk-ai

3. Inspect:

git status

4. Inspect the current repository structure.
5. Read at minimum:

AGENTS.md

backend/config.py

backend/main.py

backend/inference/base.py

backend/inference/registry.py

backend/inference/router.py

backend/inference/engines/sglang.py

backend/inference/engines/mock.py

6. Run existing tests if present.
7. Verify the current code still compiles.
8. Do NOT immediately rewrite the working inference layer.
9. Resume with the engine capability model.
10. After capability modeling is validated, proceed toward the native vLLM integration.

If repository state contradicts this checkpoint, trust the repository and Git history over this prose, investigate the difference, and preserve newer valid work.