# Kimi K3 intent and execution plan

Date: 2026-09-29
Status: owner intent clarified; implementation correction required

## Executive summary

The owner wants Ryuk to use the official `moonshotai/Kimi-K3` model published
on Hugging Face, while relying on GPU infrastructure to perform inference. The
owner does not want Ryuk's Kimi integration to depend on NVIDIA's shared
`integrate.api.nvidia.com` trial endpoint.

The recent Phase 2B work followed the wrong path. It tested NVIDIA's shared
hosted API Catalog endpoint and investigated its account readiness and timeout
behavior. That evidence is valid for that endpoint, but it does not certify the
deployment the owner intended.

No more NVIDIA API Catalog calls should be made for Kimi K3. The hosted results
should remain in Git as historical evidence and must not be presented as
certification of a Hugging Face-backed deployment.

## What the owner wants

Ryuk should:

1. Identify the model as the official Hugging Face artifact
   `moonshotai/Kimi-K3`.
2. Preserve the exact Hugging Face revision, license, tokenizer, configuration
   and model provenance.
3. Send inference through a Ryuk-owned engine interface rather than allowing a
   provider SDK or OpenAI-compatible protocol to become Ryuk's internal
   abstraction.
4. Use GPU-backed inference without requiring the local development laptop to
   load the 2.8-trillion-parameter model.
5. Keep model selection separate from inference-provider and compute selection.
6. Retain the ability to change the serving provider or move to dedicated
   NVIDIA infrastructure later without rewriting workflows, routing, auditing
   or evaluation code.

In compact form:

```text
Official Kimi K3 model identity: Hugging Face moonshotai/Kimi-K3
Inference location: remote GPU infrastructure
Ryuk responsibility: routing, policy, provenance, audit and evaluation
External service responsibility: execute the model
```

## The concepts that were confused

### 1. Hugging Face Hub model hosting

Hugging Face stores and publishes the official model files, configuration,
model card and revision history. This is the source of the model artifact and
its identity.

This alone does not mean Hugging Face is executing inference. A Hub model can
also be downloaded and served elsewhere with vLLM, SGLang or another runtime.

### 2. Hugging Face Inference Providers

The Kimi K3 page currently offers a runnable inference widget. Hugging Face
routes those requests to an external inference provider. The providers listed
for Kimi K3 during the 2026-09-29 review included Baseten, DeepInfra, Fireworks
and Together.

This path avoids downloading and operating Kimi K3 ourselves. Ryuk would use a
Hugging Face token and select or allow routing to one of those providers.

However, this path does not currently identify NVIDIA itself as the selectable
provider. An external provider may use NVIDIA GPUs internally, but that is not
the same as Ryuk controlling or attesting a specific NVIDIA deployment.

### 3. NVIDIA API Catalog hosted inference

`https://integrate.api.nvidia.com` is NVIDIA's shared hosted API Catalog
service. It serves a Kimi K3 route, but it is a separate deployment from the
Hugging Face Inference Providers routes and from a self-managed deployment of
the Hugging Face weights.

This was the target of the recent Phase 2B probes. It is not the owner's
intended Kimi path and should no longer drive the critical path.

### 4. Self-managed Kimi K3 on NVIDIA GPUs

The official Hugging Face artifact can be downloaded to NVIDIA GPU
infrastructure and served through vLLM, SGLang or NVIDIA Dynamo. This provides
the strongest control over artifact identity and compute provenance.

It is also a large infrastructure commitment. NVIDIA's published Dynamo
recipes describe configurations such as 32 H200 GPUs or 16 to 48 GB200/GB300
GPUs. An NVIDIA Developer Program API key does not itself provide this cluster.

## What the NVIDIA Developer Program can do for Ryuk

The NVIDIA Developer Program is useful to Ryuk, but its benefits must be
separated into software access, shared prototype endpoints and actual compute.

| Capability | What Ryuk can do | Important limit |
| --- | --- | --- |
| NVIDIA-hosted NIM endpoints | Prototype against models exposed at `build.nvidia.com` using free developer access or available trial credits | This uses NVIDIA's shared deployment, not a Ryuk-controlled deployment of the pinned Hugging Face artifact; it is development/testing access, not production certification |
| Downloadable NIM software | Download eligible NIM containers for research, development and testing | Availability is model-specific; program membership does not prove that a downloadable Kimi K3 NIM exists or that its artifact matches the selected Hugging Face revision |
| Self-hosted NIM license | Run eligible downloadable NIMs for research, application development and experimentation on up to 16 GPUs on owned, rented or cloud infrastructure | NVIDIA supplies the software entitlement, not the GPUs, storage, networking or cloud bill; production requires a different commercial entitlement |
| NVIDIA GPU software stack | Use CUDA, NGC artifacts, supported NIM runtimes, vLLM/SGLang integrations, observability guidance and Kubernetes deployment material | The local Ryuk development laptop cannot run full Kimi K3, and installing the software does not create remote capacity |
| LaunchPad and guided environments | Use available guided labs or development sandboxes to learn and test supported NVIDIA solutions | Availability, duration and hardware are program-dependent; this is not evidence of a persistent Kimi K3 cluster |
| Community support | Ask endpoint, entitlement and deployment questions through the NVIDIA Developer Forum | Developer Program access does not include enterprise support, an SLA or guaranteed endpoint stability |
| Training and documentation | Use DLI material, technical documentation, forums, webinars and early-access opportunities where eligible | These resources help implementation but do not activate a production deployment |

For Kimi K3 specifically, the program creates three possible uses:

1. **Shared NVIDIA prototype:** use NVIDIA's hosted Kimi K3 API Catalog route
   for experiments. Ryuk already explored this route, and repeated timeouts
   make it unsuitable as the currently certified Kimi deployment. It can remain
   an optional future candidate rather than the primary path.
2. **Bring our own compute:** use the official Hugging Face Kimi K3 artifact
   with vLLM, SGLang or Dynamo on NVIDIA GPUs obtained separately. Developer
   Program software rights can help with development and testing, but Ryuk must
   still obtain and pay for the hardware. NVIDIA's documented Kimi K3 recipes
   include some 16-GPU GB200/GB300 layouts that fit the program's stated
   16-GPU software-use ceiling, as well as larger layouts that do not.
3. **Hugging Face serverless/dedicated route:** NVIDIA documents that selected
   serverless NIM endpoints can be reached through Hugging Face and that
   dedicated endpoints can be launched in a preferred cloud. This must be
   verified for the exact Kimi K3 deployment. The current Hugging Face Kimi K3
   provider comparison lists Baseten, DeepInfra, Fireworks and Together, not
   NVIDIA, so Ryuk must not claim NVIDIA processing from the Hugging Face route
   without additional provider evidence.

The Developer Program therefore remains valuable even if Ryuk initially uses
Hugging Face Inference Providers: it supplies NVIDIA development tools,
prototype endpoints, NIM software access, documentation and a later migration
path to controlled NVIDIA compute. It does **not** make Hugging Face inference
free, provide a large Kimi cluster automatically, or prove that a third-party
Hugging Face provider used a particular NVIDIA runtime or GPU topology.

### Recommended role of the program in Ryuk

Ryuk should treat the NVIDIA Developer Program as an optional compute and
runtime enablement program, not as the source of Kimi K3's model identity.

```text
Model identity and revision       Hugging Face moonshotai/Kimi-K3
Initial remote inference option   Hugging Face Inference Provider
NVIDIA development option         Shared NIM prototype endpoint
NVIDIA controlled-deploy option   NIM/vLLM/SGLang/Dynamo on separately obtained GPUs
Production entitlement            Separate approval and commercial terms
```

Each line is a separate profile with separate provenance and acceptance
evidence. Ryuk may rank them as candidates later, but it must not merge their
identities or capabilities.

## Recommended initial interpretation

The most direct interpretation of the owner's statements is:

```text
Use the official Hugging Face Kimi K3 identity.
Use Hugging Face's already-available remote inference path initially.
Do not download or self-host the full model now.
Do not use NVIDIA's shared API Catalog Kimi endpoint.
Keep a future dedicated NVIDIA deployment as a separate deployment profile.
```

This is the shortest path to using the model without procuring a very large GPU
cluster. It also preserves Ryuk's vendor-independent architecture if the new
adapter is kept at the external boundary.

There is one limitation that must be stated honestly: the currently listed
Hugging Face Kimi providers are third parties. Ryuk cannot claim that a request
was processed by a specific NVIDIA deployment unless the selected provider
supplies acceptable hardware/runtime evidence.

## One decision still required

The owner must choose which statement is the actual requirement:

### Option A — Use Kimi through Hugging Face now

Use Hugging Face Inference Providers and one of the available Kimi K3
providers. This requires no self-managed GPU cluster. It may incur provider
charges, and the current Ryuk USD 0 ceiling must remain in force until credits
or an explicit budget are confirmed.

### Option B — Require verified NVIDIA compute

Use the Hugging Face model artifact but deploy it on identified NVIDIA GPU
infrastructure under Ryuk's control. This requires access to a suitably large
GPU cluster, storage, networking, a supported runtime and an approved budget.

The phrase "from Hugging Face and processed by NVIDIA" describes Option B if
verified NVIDIA compute is a hard requirement. The phrase "already hosted on
Hugging Face" describes Option A if avoiding deployment is the priority.

The two options use the same model identity but are different deployments with
different credentials, costs, evidence and operational responsibilities.

## Required repository corrections

After the owner chooses Option A or Option B:

1. Add a superseding decision record rather than rewriting historical
   decisions silently.
2. Mark `DEC-001`'s NVIDIA API Catalog hosted-first choice as superseded for
   Kimi K3.
3. Stop the current P2B-002 through P2B-005 NVIDIA-hosted Kimi workstream and
   retain its records as historical endpoint evidence.
4. Create an immutable deployment profile with:
   - model artifact `moonshotai/Kimi-K3`;
   - an exact Hugging Face commit revision;
   - the Kimi K3 license and model-card sources;
   - a separate deployment/provider identity;
   - explicit unknown fields where the provider does not expose runtime,
     hardware or artifact-digest evidence.
5. Implement a dedicated external adapter:
   - Option A: Hugging Face Inference Providers adapter;
   - Option B: native vLLM, SGLang or Dynamo worker adapter on NVIDIA compute.
6. Keep provider request formats inside that adapter. Ryuk's internal contract
   remains `InferenceRequest -> InferenceEngine -> InferenceResponse`.
7. Add offline contract fixtures and tests before any live request.
8. Define identity, timeout, cancellation, usage and structured-output evidence
   for the selected deployment.
9. Reconfirm the budget. Do not infer that a runnable Hugging Face widget is
   free or that an NVIDIA Developer Program key grants GPU capacity.
10. Run one bounded synthetic smoke test only after credentials, provider,
    budget and acceptance criteria are approved.

## What the owner needs to do now

The owner should answer only this question:

> Should Ryuk use Hugging Face Inference Providers now, even though the
> selectable Kimi providers are third parties, or must inference run on a
> specifically identified NVIDIA GPU deployment?

No API key should be pasted into chat. No new credential or paid resource is
needed until that choice is made.

## Sources checked on 2026-09-29

- Official Kimi K3 Hugging Face model:
  `https://huggingface.co/moonshotai/Kimi-K3`
- Hugging Face Inference Providers documentation:
  `https://huggingface.co/docs/inference-providers/index`
- Current Kimi K3 provider comparison:
  `https://huggingface.co/inference/models?model=moonshotai%2FKimi-K3`
- NVIDIA Dynamo Kimi K3 deployment recipe:
  `https://docs.nvidia.com/dynamo/dev/recipes/kimi-k3`
- NVIDIA API Catalog Kimi K3 model card:
  `https://build.nvidia.com/moonshotai/kimi-k3/modelcard`
- NVIDIA Developer Program benefits:
  `https://developer.nvidia.com/developer-program`
- NVIDIA NIM Developer Program scope and deployment options:
  `https://docs.api.nvidia.com/nim/docs/run-anywhere`
- NVIDIA NIM Developer Program FAQ:
  `https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317`

## Bottom line

The model, the inference service and the hardware are three separate choices.
The official Kimi K3 model is on Hugging Face. Hugging Face can route inference
to an available provider. Verified NVIDIA processing requires a distinct
NVIDIA-backed deployment and evidence. Ryuk must represent these as separate
objects instead of treating any one of them as proof of the others.
