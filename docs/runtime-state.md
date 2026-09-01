# Runtime-State Collection

D2 separates stable deployment capabilities from short-lived runtime
observations. `RuntimeStateCollector` probes deployments concurrently on an
application-owned background task. Each probe is bounded, and snapshots are
immutable, timestamped, and expire after a configured TTL.

Liveness, readiness, admission, and capacity remain distinct. Unknown or stale
state is not routable. The router and `/inference/engines` read the cache and do
not perform request-path health probes, so one slow worker cannot delay them.

Execution attempts feed a bounded 20-attempt summary with recent failure rate,
last latency, and last failure code. Capacity failures reject admission;
deployment-unavailable failures mark the worker down. Later successful probes
or attempts restore applicable state. This is local circuit input, not a
distributed circuit breaker.

Prometheus metrics remain observational inputs and never determine whether an
individual inference transaction succeeded.
