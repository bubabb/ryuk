# P2B-002 NVIDIA account-evidence collection runbook

Date: 2026-09-28
Status: operator action required; no provider record collected

## Purpose

Collect the account-specific evidence required by DEC-007 without placing an
NVIDIA credential, account identifier, screenshot, support transcript or other
sensitive provider content in the Ryuk repository.

NVIDIA documents that NGC organizations manage access to NGC services, that the
`Public API Endpoints User` role controls access to API Catalog NIM endpoints,
and that personal-key permissions derive from the user's organization grants.
See the official [NGC User Guide](https://docs.nvidia.com/ngc/latest/ngc-user-guide.html).
The public documentation reviewed for this task did not expose a supported
read-only API returning the required account-to-route mapping and recent-request
disposition. Use the authenticated UI or NVIDIA provider support; do not probe
undocumented account endpoints.

## Operator prerequisites

- Access to the NVIDIA/NGC account that issued the protected key used by Ryuk.
- Permission to view the organization, API-key service grants, API Catalog
  routes and recent request/support information.
- A secure location outside the repository for the source screenshot, export or
  provider-support response.
- Synthetic/public-only scope and the USD 0 paid-spend ceiling remain active.

Do not rotate, regenerate, broaden, deactivate or reveal a key merely to collect
this evidence. Stop if the UI requests payment, subscription activation or paid
provisioning.

## Collection steps

1. Sign in to the NGC organization that owns the key. Confirm the organization
   is the intended Ryuk account without copying its raw name or number into the
   repository.
2. Confirm the key or user has the documented API Catalog NIM/public-endpoint
   grant. Record only whether the grant is present; never capture the key value.
3. In the authenticated API Catalog/account surface, verify whether each exact
   route is visible to this account:
   - `moonshotai/kimi-k3`
   - `deepseek-ai/deepseek-v4.1-flash`
4. Record the displayed entitlement for each route as `free`, `paid` or
   `unknown`. Anything except `free` fails the current USD 0 gate.
5. Record the displayed readiness for each route as `ready`, `not_ready` or
   `unknown`. Do not translate catalog visibility into readiness.
6. If the account surface exposes recent requests, classify the latest relevant
   request for each route as `completed`, `pending`, `rejected`, `timed_out`,
   `not_observed` or `unknown`. Do not copy request IDs, prompt/output content,
   error bodies or reasoning.
7. If the UI does not expose route mapping or request disposition, ask NVIDIA
   support to confirm the same fields. Do not ask support to reveal protected
   payloads or credentials.
8. Save the source artifact outside the repository with restricted access.
   Record its SHA-256 digest; do not copy the artifact into Git.
9. Create a stable, non-secret label for the account/project and record only the
   lowercase SHA-256 digest of that label. Do not use an email address, account
   number, organization name or project name as the stored value.
10. Prepare a JSON document matching
    `scripts.validate_nvidia_account_evidence.NvidiaAccountEvidence`. Do not add
    notes or free-form provider text; the closed schema will reject them.
11. Validate locally:

    ```text
    python scripts/validate_nvidia_account_evidence.py /secure/path/evidence.json
    ```

12. Review the printed summary. It intentionally omits both hashes. Exit status
    zero means the account mapping is structurally complete and both routes are
    reported visible, free-entitled and ready. It does not prove source
    authenticity or live served identity.

## Evidence acceptance checklist

- Source is an authenticated dashboard or identifiable provider-support record.
- Observation has an explicit timezone-aware timestamp.
- Account reference and retained artifact are represented only by distinct
  lowercase SHA-256 digests.
- Both configured model IDs exactly match the provider route IDs.
- Both routes are account-visible, free-entitled and ready.
- Recent-request disposition is explicit even when it is `unknown` or
  `not_observed`.
- No credentials, headers, raw account identifiers, request IDs, prompts,
  outputs, reasoning, error bodies, screenshots or support text enter Git.
- A separate live response must still report the exact configured served-model
  ID for each route. The account record cannot replace that DEC-007 condition.

## Decision after validation

- If the mapping validator fails, retain P2B-002 as `BLOCKED` and do not run
  another Kimi request.
- If it passes but Kimi live response identity remains unavailable, retain
  P2B-002 as `BLOCKED`; use the provider record to form a new diagnostic
  hypothesis before seeking explicit authorization for another bounded call.
- If account mapping and both exact live response identities pass, review the
  combined evidence against DEC-007 before changing P2B-002. Passing the local
  validator alone never activates a deployment.
