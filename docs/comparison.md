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

### Lab Memory Agent (planned)
_Fill in after build._
- DX impressions:
- Eval results:
- Cost (€/mo):
- Verdict:

### NauroLabs Watcher (not started)

### AgentMode Dataset Curator (not started)

### Idea Validator (not started)

### Receipt Processor (not started)
