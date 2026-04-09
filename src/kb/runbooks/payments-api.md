# Payments API — Incident Triage Runbook

## Service overview
- Handles payment authorization and charge processing
- Critical upstream dependencies: payment provider gateway, fraud-detection service
- Primary endpoint under load: `/charge`
- Typical p95 latency: 250–380 ms; alert threshold: >800 ms

## Step 1 — Correlate with deploy timeline
Before any remediation, check whether the incident window coincides with a deployment:
- Query the deploy log for `payments-api` within the last 2 hours
- If a deploy occurred within 15 minutes of the incident start, treat it as the primary suspect
- Cross-reference with upstream payment provider status page

## Step 2 — Diagnose error distribution
- Distinguish 5xx from payment provider timeouts vs. application-level errors
- If `PaymentProviderTimeout` dominates: upstream issue; hold rollback; escalate to provider
- If `RetryBudgetExceeded` dominates: retry saturation from cascading timeout — rate-limit or shed load
- If `UpstreamDependencyUnavailable`: check fraud-detection service health

## Step 3 — Check retry saturation
- Elevated retry rate amplifies upstream load; verify retry budget metrics
- If retries are exhausted, the service is shedding load — this is a leading indicator of full outage

## Step 4 — Rollback criteria
Only initiate rollback when ALL of the following are true:
1. A deploy occurred within the incident window
2. Error rate is >10% and not explained by upstream provider degradation
3. Rollback has been reviewed and approved by an on-call lead

## Step 5 — Escalation
- P1 incidents: page payment-platform on-call within 5 minutes
- If provider is confirmed degraded: notify partner-success team for customer communication
