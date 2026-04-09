# Auth Service — Incident Triage Runbook

## Service overview
- Handles user authentication (login, token refresh, session validation)
- Critical dependencies: user-db, token store (Redis), identity provider (IdP)
- Primary endpoint: `/login`, `/refresh`
- Typical login success rate: >99.5%; alert threshold: failure rate >2%

## Step 1 — Check identity provider status
- Auth failures often originate from IdP degradation, not the auth-service itself
- Check IdP status page and IdP connectivity from the service
- If IdP is degraded: auth-service cannot self-heal; escalate to IdP vendor

## Step 2 — Check token store health
- Redis unavailability causes token validation to fail for all active sessions
- Check Redis memory, connection count, and replication lag
- If Redis is saturated: enable token store fallback mode (stateless JWT verification only)

## Step 3 — Check user-db connectivity
- Login failures with `db_timeout` error code indicate user-db overload or network issue
- Review connection pool saturation and query latency on user-db

## Step 4 — Regional isolation
- EU region may have a separate IdP endpoint; check region-specific config
- Verify that EU traffic is not routing through US-west endpoints due to DNS misconfiguration

## Step 5 — Rollback criteria
- Auth-service rollback is high-risk (invalidates active sessions)
- Only roll back if a code-level bug is confirmed (not a dependency issue)
- Requires approval from security on-call in addition to SRE lead
