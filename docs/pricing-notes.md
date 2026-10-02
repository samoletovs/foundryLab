# Pricing Notes — actual cost observations

Update after each Azure billing cycle. The 2026-10-02 approved pilot uses a
$15/calendar-month **shared model account** ceiling and a $10/month incremental
pilot target inside the lab's $80/credit-cycle total ceiling. These are spending
controls, not the Azure credit balance; native-currency alerts remain separate.

## Model-refresh pilot (2026-10-02)

Azure retail API, Sweden Central, Global Standard, short-context USD per million:

| Deployment | Uncached input | Cached input | Output |
|------------|----------------|--------------|--------|
| `gpt-6-luna` (`2026-09-22`) | $0.10 | $0.01 | $0.50 |
| `gpt-6-sol` (`2026-09-22`) | $2.00 | $0.20 | $10.00 |

Output includes reasoning tokens. Cache writes, long-context requests and tool
charges can increase the bill. Never apply the historical cached-mini blended
rate below to these models or all shared-account tokens.

The initial capacity-10 smoke deployments exposed only 10,000 tokens/minute,
too small for existing bounded long prompts. Shared Luna therefore has capacity
100 and Sol 50; this allocates quota without a fixed idle inference charge.
Supported old deployments remain explicit rollback options during verification.
Use `scripts/evaluate_model_refresh.py` for bounded synthetic JSON and tool
compatibility checks. A five-case smoke gate is not evidence of better product
quality; compare real task fixtures before expanding a premium workload.

Live migration checks found that Sol function tools on Chat Completions require
`reasoning_effort='none'`; use `low` only for pure synthesis. Both use
`max_completion_tokens`. GPT-4o-mini transcription is pinned to `2025-12-15`,
not the retiring `2025-03-20` version.

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

### 2026-05-09 — Phase 1+2+3 complete
- Ingested 56 files / 689 KB into Foundry vector store
- File search storage: under the 1 GB free threshold → €0 storage
- gpt-4o-mini deployment capacity bumped from 50 → 200 (no $ change)
- Eval cycles ran (baseline + optimized): ~30 file_search calls × ~10K tokens = ~300K tokens = ~€0.06
- Prompt optimizer call: ~3K tokens = ~€0.001
- Cumulative spend so far: ~€0.10 across all 3 phases
- Embedding deployment unused — Foundry Basic uses MS-managed embeddings.
  Idle cost remains €0.

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
