# Inventory API — Incident Triage Runbook

## Service overview
- Serves product availability lookups for checkout and catalog
- Critical dependencies: read replica database, SKU cache (Redis)
- Primary endpoint: `/availability`
- Typical p95 latency: 100–200 ms; alert threshold: >350 ms

## Step 1 — Check read replica lag
- Elevated latency almost always traces to replica lag on the inventory database
- Query `pg_stat_replication` or the replica-lag dashboard; lag >5 s is abnormal
- If lag is high: traffic may need to be redirected to primary (read load increases risk)

## Step 2 — Check cache miss storm
- A cache miss storm after a deploy or cache flush causes sudden read amplification
- Look for `CacheMissStorm` in logs around the incident start
- If cache hit rate dropped sharply, pre-warm the cache before restoring traffic

## Step 3 — Correlate with deploy
- A schema migration or config change can invalidate the cache or increase replica lag
- Confirm whether a deploy coincided with the latency spike

## Step 4 — Rollback criteria
Rollback is warranted only when:
1. A deploy is confirmed to correlate with the spike
2. Replica lag is not the primary driver
3. Rolling back does not risk a second cache invalidation storm (verify with DBA)

## Step 5 — Load shedding
- If p95 exceeds 600 ms, enable request throttling for non-critical paths (batch jobs, analytics)
- Protect checkout traffic above catalog browsing traffic
