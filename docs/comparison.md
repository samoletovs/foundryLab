# Foundry vs. Alternatives — Living Comparison

This file is the **artifact** of foundryLab. Update it after every agent build.

Cells marked `?` mean "not yet evaluated". Cells with concrete observations should
link to the agent that produced the evidence.

## Comparison matrix

| Dimension | Microsoft Foundry | Copilot Studio | Custom Azure Functions + AOAI | VS Code Skills |
|-----------|-------------------|----------------|-------------------------------|----------------|
| **Time to first running agent** | ? | ? | ~2h (proven in agentMode) | ~10 min |
| **Lines of code for "hello agent"** | ? | 0 (low-code) | ~50 | ~30 (markdown) |
| **Cost — idle** | ? | seat-based (~$200/user/mo) | $0 (consumption) | $0 |
| **Cost — light usage** | ? | seat-based | ~$1–5/mo | $0 |
| **Built-in evals** | ✅ batch + continuous | partial (analytics) | ❌ build yourself | ❌ |
| **Prompt optimization** | ✅ built-in | ❌ | ❌ build yourself | ❌ |
| **Multimodal (vision/audio)** | ✅ | ✅ | ✅ via AOAI | partial |
| **Knowledge grounding (RAG)** | ✅ file search + vector store | ✅ SharePoint-centric | ❌ build yourself (AI Search) | ❌ |
| **Multi-agent orchestration** | ✅ connected agents | partial | ❌ build yourself | partial (subagents) |
| **Tool calling** | ✅ | ✅ (low-code) | ✅ (raw) | ✅ (MCP) |
| **Tracing / observability** | ✅ built-in + App Insights | ✅ (basic) | ✅ App Insights manual | ❌ |
| **Deploy/CI** | azd / Bicep | portal | Bicep / azd | git only |
| **Portability (export to other runtime)** | low–medium | low | high | high |
| **Best for** | ? | citizen devs / Microsoft 365 | full control, low cost | dev-loop tooling |
| **Worst for** | ? | code-heavy logic | quick experiments | production agents |

## Decision flowchart (draft — refine as we learn)

```
Need agent →
  Is it dev-loop only (no end users)?      → use VS Code Skill
  Is it for Microsoft 365 / business users? → consider Copilot Studio
  Need: RAG + evals + optimizer?            → Foundry
  Need: low cost + full control + tiny scope? → custom Functions + AOAI
  Need: multimodal + scheduled job?         → ?
```

## Per-agent observations

### Lab Memory Agent (final, 4-phase iteration complete)
- **DX impressions:** Foundry's Basic agent setup eliminates RAG plumbing —
  we wrote 0 lines of chunking, embedding, or vector-DB code. Compare to a
  custom Azure stack: AI Search index + skillset + per-file embedding job
  + retrieval client + result reranking ≈ days of work for the same
  outcome. Total foundryLab time spent on labMemoryAgent: ~7 hours
  including all troubleshooting, provisioning, and 4 eval cycles.
- **Eval results across 4 runs (15-item golden dataset):**
  | Metric | Baseline | Optimized prompt | + Path headers + small chunks | **+ temperature=0.2 (final)** |
  |---|---|---|---|---|
  | cited_expected | 0.67 | 0.67 | 0.83 | **0.92** |
  | citation_recall | 0.56 | 0.51 | 0.69 | **0.75** |
  | has_citations | 0.83 | 1.00 | 1.00 | 0.92 |
  | refusal_accuracy | 1.0 | 1.0 | 1.0 | 1.0 |
  | Mean latency | 7.1s | 6.7s | 5.8s | 6.5s |
- **Foundry prompt-optimizer experience:** MCP tool was unusable due to
  per-session auth caching. Wrote our own ~150 LOC optimizer that
  performed identically. Foundry-specific value: the file_search service
  itself (auto-chunking, auto-embedding) and the persistent agent
  abstraction.
- **Cost (€/mo):** € 0 idle. Eval cycles cost ~€0.05 each. Cumulative
  spend across all phases <€0.20. Estimated <€2/mo at planned query volumes.
- **Verdict:** For < 1 GB private corpora with mostly markdown, Foundry
  Basic file_search is a clear win over rolling your own RAG.
  Final caveats:
  1. Foundry strips path prefixes from filenames — embed paths into
     content (we use `# Source: <path>` headers).
  2. Default temperature gives stochastic answers — set `temperature=0.2`
     when creating the agent.
  3. Smaller chunks (500/120 tokens) outperform the default for short
     markdown docs.
  4. Agent runtime can be inconsistent with newly-deployed models
     (we hit `invalid_deployment` errors on gpt-4o despite REST working).
     Deploy all candidate models in Phase 0 Bicep, not later.
  5. The eval framework is portable Python; not Foundry-specific. Keep
     it independent so we can swap in any agent backend.

### NauroLabs Watcher (not started)

### AgentMode Dataset Curator (not started)

### Idea Validator (not started)

### Receipt Processor (not started)
