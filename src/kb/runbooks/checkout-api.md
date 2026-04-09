# Checkout API — Incident Triage Runbook

## Service overview
- Orchestrates the end-to-end order submission flow
- Critical dependencies: payments-api, inventory-api, order-db
- Primary endpoint: `/submit-order`
- Typical p95 latency: 220–350 ms; alert threshold: >700 ms

## Step 1 — Identify failure mode
- `OrderSubmissionTimeout`: checkout waited too long for a downstream response
- `PaymentAuthorizationUnavailable`: payments-api is degraded (see payments-api runbook)
- `RetryBudgetExceeded`: retry storm consuming downstream capacity

## Step 2 — Check downstream dependency health
- payments-api and inventory-api are the most common failure sources for checkout
- Check their error rates and latency before investigating checkout itself
- If downstream is degraded: checkout cannot recover independently

## Step 3 — Retry storm mitigation
- Checkout retries failed payment authorizations with exponential backoff
- If retry budget is exhausted, the service is amplifying load on payments-api
- Consider circuit-breaking the payments-api connection to shed retry pressure

## Step 4 — Order-db check
- Rarely the primary cause, but a slow order-db write will manifest as `OrderSubmissionTimeout`
- Check order-db write latency and lock contention

## Step 5 — Rollback criteria
- Roll back checkout only when the issue is isolated to a checkout deploy (not downstream)
- Coordinate rollback with payments and inventory on-call; a partial rollback can leave orders in inconsistent state

## Step 6 — Customer impact
- Failed orders generate immediate customer support volume
- Notify customer-success within 10 minutes of a P1 checkout outage
