# CONFIG — runtime limits (PoC)

## 1) Time & tool budgets
- `p95_ttfa_target_s = 30`
- `max_tool_calls = 6`
- `tool_timeout_s = 3`
- `max_retries = 2`
- `time_budget_s = 30` (soft)

## 2) LLM settings (PoC)
- `temperature = 0..0.2` (reproducibility)
- `max_output_tokens = ...`
- prompt policy: cite-or-ask

## 3) Safety
- `pii_redaction_enabled = true`
- `write_tools_enabled = false` (PoC)