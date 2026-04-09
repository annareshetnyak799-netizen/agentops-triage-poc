# Deployment — PoC Topology

```mermaid
flowchart LR
    U[User / On-call]

    subgraph HOST[PoC Host]
        API[API / Orchestrator Container :8000]
        STORE[(SQLite Volume /app/data)]
        OBS[Stdout Logs + /metrics + /ready]
    end

    subgraph EXT[External Dependencies]
        LLM[LLM Provider API]
        MET[Metrics Backend]
        LOG[Logs Backend]
        KB[Runbook KB]
    end

    U --> API
    API --> STORE
    API --> OBS

    API --> LLM
    API --> MET
    API --> LOG
    API --> KB
```

## Minimal container packaging

The current PoC packaging assumes:
- one application container built from the repo `Dockerfile`;
- one persistent Docker volume for SQLite state;
- bridge-network access from the app container to external APIs;
- environment-based configuration through `.env` and `docker-compose.yml`.

Resource limits are intentionally lightweight for the PoC:
- CPU and memory limits are not hard-pinned in Compose by default;
- bounded runtime behavior is enforced primarily by app-level limits:
  - `max_tool_calls`
  - `tool_timeout_s`
  - `time_budget_s`

If stricter infra constraints are needed later, Docker Compose can be extended with:
- `mem_limit`
- `cpus`
- explicit healthcheck
- separate observability sink
