# ARCHITECTURE — AgentOps Triage PoC

## 1. Purpose

This document describes the target architecture of the **AgentOps Triage PoC** and serves as an implementation-oriented handoff artifact for engineering work.

The goal of the system is to accept an incident description, run a bounded agentic triage loop, collect evidence from tools and knowledge sources, apply safety and governance constraints, and return a structured triage report with:
- hypotheses,
- prioritized next steps,
- evidence references,
- safety notes,
- optional approval-required actions.

This is a **read-mostly / safe-by-default PoC**. Destructive or write actions are disabled by default or require explicit approval.

---

## 2. Scope

### In scope
- Incident intake API
- Session-oriented triage execution
- Tool-calling orchestration loop
- Read-only operational tools
- Knowledge retrieval
- Safety gates and policy checks
- Session state and trace persistence
- Metrics, logs, traces
- Offline eval harness

### Out of scope
- Fully autonomous remediation
- Production-grade multi-tenant RBAC
- Direct write access to real infrastructure by default
- Complex long-term memory across organizations
- Full incident management workflow replacement

---

## 3. High-level system goals

The architecture is designed to support the following goals:

1. **Fast first response**  
   Return a useful first structured triage plan within target TTFA.

2. **Evidence-grounded reasoning**  
   Agent outputs must be backed by tool observations and/or KB references.

3. **Bounded autonomy**  
   The system may reason and investigate, but must not execute risky actions without policy approval.

4. **Operational safety**  
   Prevent PII leakage, unsafe tool usage, prompt injection propagation, and unsupported claims.

5. **Observability-first design**  
   Every triage session should be inspectable through logs, traces, tool-call metadata, and evaluation artifacts.

6. **PoC-friendly implementation**  
   Simple enough to build quickly, but structured so it can evolve into a service-oriented platform later.

---

## 4. Primary use case

**Main scenario:**  
An engineer or incident commander submits an incident, for example:

- “High 5xx rate in payments-api”
- “Latency spike after deploy”
- “Customer reports login failures in EU region”

The system should:
1. create a triage session,
2. classify the incident,
3. propose an investigation plan,
4. call relevant tools,
5. gather observations,
6. refine hypotheses,
7. produce a structured triage report,
8. flag actions that require human approval.

---

## 5. Architectural principles

### 5.1 Safe by default
The system defaults to read-only investigation. Any action that may modify state, trigger automation, or affect production requires explicit approval and separate policy handling.

### 5.2 Evidence before conclusion
The agent should prefer:
- observed metrics,
- retrieved runbooks,
- known incidents,
- tool results,
over unsupported free-form speculation.

### 5.3 Small bounded loops
The PoC should limit:
- number of agent iterations,
- number of tool calls,
- time budget per session,
- token budget.

This reduces cost, latency, and unsafe drift.

### 5.4 Clear separation of concerns
The architecture separates:
- API handling,
- orchestration,
- safety,
- tools,
- knowledge retrieval,
- persistence,
- observability,
- evaluation.

### 5.5 Replayability
A session should be reproducible enough for debugging and evals:
- same input,
- same tool traces,
- same policy checks,
- same final report structure.

---

## 6. System context

### Actors
- **On-call engineer / incident commander** — submits incident, reviews output
- **LLM-powered triage agent** — plans and coordinates investigation
- **Operational tools** — monitoring/log/search systems
- **Knowledge base** — runbooks, incident docs, service metadata
- **Policy / safety layer** — constrains and validates outputs
- **Eval harness** — measures quality offline

### External systems (PoC examples)
- Metrics backend
- Logs backend
- Runbook/document store
- Service catalog / CMDB mock
- Incident history store (optional/mock)

---

## 7. Logical architecture

```mermaid
flowchart LR
    U[User / IC / On-call Engineer] --> API[API Layer]

    API --> ORCH[Orchestrator]
    ORCH --> SAFE[Safety & Policy Layer]
    ORCH --> MEM[Session State Manager]
    ORCH --> RETR[Knowledge Retrieval]
    ORCH --> TOOLS[Tool Executor]
    ORCH --> LLM[LLM Provider Adapter]

    RETR --> KB[Runbooks / KB / Incident Docs]
    TOOLS --> OBS[Metrics / Logs / Service Catalog Tools]

    ORCH --> REPORT[Structured Triage Report Builder]
    REPORT --> API

    ORCH --> TELE[Telemetry / Logs / Traces / Metrics]
    SAFE --> TELE
    TOOLS --> TELE
    RETR --> TELE

    EVAL[Offline Eval Harness] --> API
    EVAL --> REPORT
    EVAL --> TELE
```
