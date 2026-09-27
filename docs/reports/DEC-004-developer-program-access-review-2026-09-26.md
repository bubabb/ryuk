# DEC-004 Developer Program access review

Date: 2026-09-26
Decision: accepted; P2B-001 ready

## Outcome

The owner authorized NVIDIA Developer Program free resources for the whole
project's development, prototyping, testing, and evaluation work. Current paid
spend is capped at USD 0. A future paid service is possible only after a new,
explicit decision defines its scope and finite spending ceiling.

Controlled Phase 2B checks may receive an NVIDIA credential through a protected
local environment variable. No repository secret manager is required now. The
credential value must not appear in Git, chat, fixtures, arguments, logs,
reports, or test output.

## Review

- The authorization is limited to account-visible free entitlements and
  synthetic/public inputs.
- Payment requests, paid credit purchases, subscriptions, paid GPU/cloud
  provisioning, missing entitlements, and ambiguous pricing are hard stops.
- Production traffic and private/customer data remain unauthorized.
- Existing chat-shared OpenAI credentials are not applicable and remain
  prohibited from repository use.
- Official NVIDIA NIM documentation currently describes free Developer Program
  endpoint access for prototyping and downloadable NIM access for development
  and testing: https://docs.api.nvidia.com/nim/docs/product. P2B-001/P2B-002
  must still capture sanitized account-specific entitlement evidence.

## Tracker decision

DEC-004 is `DONE`. P2B-001 moves from `BLOCKED` to `READY` because its policy
dependencies are resolved; it is not itself complete. No endpoint was contacted,
no credential was received, and no spend or provisioning occurred in this
change.
