# Pricing Notes — actual cost observations

Update after each Azure billing cycle. Goal: total foundryLab spend ≤ €10/mo.

## Estimated baselines (before measurement)

| Component | Unit cost | Why we expect it |
|-----------|-----------|------------------|
| GPT-4o-mini input | $0.15 / 1M tokens | Foundry default model |
| GPT-4o-mini output | $0.60 / 1M tokens | |
| GPT-4o input | $2.50 / 1M tokens | Used only when mini fails quality gate |
| GPT-4o output | $10.00 / 1M tokens | |
| File search (vector store) | $0.10 / GB / day | Lab Memory Agent storage |
| Code Interpreter session | $0.03 / session | Avoid unless needed |
| Bing Grounding | $35 / 1000 queries | **Avoided** — use direct fetch |
| App Insights | first 5 GB free / mo | All foundryLab agents share one |
| Container Apps Job | ~$0.000024 / vCPU-sec | Used for scheduled hosted agents |

## Per-agent budget targets

| Agent | Target €/mo | Driver |
|-------|-------------|--------|
| Lab Memory Agent | €2–3 | vector store + retrieval |
| NauroLabs Watcher | €1–2 | weekly scans + daily ops calls |
| AgentMode Dataset Curator | €2 | weekly batch evals |
| Idea Validator | €1 | on-demand only |
| Receipt Processor | €0.50 | low volume + small images |
| **Total target** | **≤ €10** | |

## Actual observations

_Fill in after each month._

### 2026-05 (foundryLab not yet deployed)
- Spend: €0
- Notes: scaffold only

### 2026-05-09 — Phase 0 deployed (idle baseline)
- Resources: AI Services account, project, 2 model deployments (GlobalStandard),
  Log Analytics, App Insights, UAMI
- **Idle cost: €0** (consumption SKUs, first 5 GB/mo Log Analytics free)
- One smoke-test inference: 22 tokens total ≈ €0.000004
- Region: `swedencentral` (overrides workspace default — see learnings.md)

### Template for future months
```
### 2026-MM
- Total Foundry spend: €X.XX
- Per-agent breakdown:
  - labMemoryAgent: €X.XX
  - …
- Surprises: …
- Optimizations applied: …
```

## Cost-spike triggers (alert if any of these happen)

- Vector store > 1 GB → file search bill jumps
- Switching any agent to GPT-4o without eval justification
- Always-on container instead of scheduled trigger
- Continuous eval running every minute instead of every hour/day
- Bing Grounding accidentally enabled
