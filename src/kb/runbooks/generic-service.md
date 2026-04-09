# Generic Service — Incident Triage Runbook

## Step 1 — Correlate with deploy timeline
- Retrieve deploy history for the affected service within the last 2 hours
- If a deploy occurred within 15 minutes of the incident start, treat it as the primary suspect

## Step 2 — Identify failure concentration
- Is the error rate uniform across all endpoints, or concentrated on one?
- Endpoint-specific failures suggest a code or config change; broad failures suggest infrastructure

## Step 3 — Check upstream and downstream dependencies
- Map direct dependencies and check their health dashboards
- Upstream degradation propagates downstream and may not be fixable by this service's team

## Step 4 — Assess retry saturation
- High retry rates amplify load on already-degraded dependencies
- If retry saturation is confirmed, enable circuit breaker or reduce timeout to shed load faster

## Step 5 — Rollback decision
- Rollback is appropriate when a deploy is clearly correlated and upstream health is normal
- Rollback requires confirmation from on-call lead; document the decision in the incident channel

## Step 6 — Escalation
- P1: engage SRE on-call and service owner within 5 minutes
- P2: notify service owner; SRE on standby
