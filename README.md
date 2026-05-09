# foundryLab — Microsoft Foundry experiment hub

A NauroLabs research project to learn Microsoft Foundry by building real agents,
and to **compare** it against alternative approaches: Copilot Studio, custom Azure
Functions + OpenAI, and Claude Agent SDK.

This is **not a product**. It's a learning lab. Each agent here exists to answer
a specific question about Foundry's capabilities, cost, and developer experience.

## Why foundryLab exists

NauroLabs already runs custom agents (`agentMode/`, the `nauro-*` skills).
The open question: **when is Foundry the right tool, and when is it overkill?**

We answer it by building 5 agents in priority order, recording learnings as we go.

## Status

| # | Agent | Folder | Status | Goal |
|---|-------|--------|--------|------|
| 1 | Lab Memory Agent | [agents/labMemoryAgent](./agents/labMemoryAgent/) | 📋 planned | Test RAG / knowledge grounding |
| 2 | NauroLabs Watcher | _not started_ | — | Test scheduled hosted agents |
| 3 | AgentMode Dataset Curator | _not started_ | — | Test evals + prompt optimizer |
| 4 | Idea Validator | _not started_ | — | Test connected multi-agent |
| 5 | Receipt Processor | _not started_ | — | Test multimodal vision |

See [docs/vision.md](./docs/vision.md) for full plan and rationale.

## Structure

```text
foundryLab/
├── README.md                 # this file
├── AGENTS.md                 # agent guidance for AI tools
├── .env.example              # shared env template
├── .gitignore
├── docs/                     # cross-cutting learning notes
│   ├── vision.md             # why foundryLab, what we're answering
│   ├── comparison.md         # Foundry vs Copilot Studio vs custom Azure
│   ├── pricing-notes.md      # actual cost observations
│   └── learnings.md          # running log of insights
├── agents/                   # one folder per Foundry agent
│   └── labMemoryAgent/       # agent #1 — first build
├── shared/                   # shared infra + helpers (created when needed)
└── scripts/                  # cross-agent scripts (created when needed)
```

## Conventions

- **One Foundry project, one resource group** (`foundrylab-rg`, `northeurope`)
- **One App Insights** for all agents (centralized observability)
- **Each agent isolated** under `agents/<name>/` with its own README, evals, infra
- **Cost cap target**: total of all agents ≤ €10/month
- **Default model**: `gpt-4o-mini`. Upgrade per-agent only if quality demands it.

## Tech stack

- Microsoft Foundry (agents + evals + datasets)
- Azure OpenAI (`gpt-4o-mini` default)
- Bicep for any custom Azure resources
- Python 3.11 (Foundry SDK)
- DefaultAzureCredential everywhere — no API keys

## Environment

- Azure subscription: Visual Studio Enterprise (`146099412+samoletovs@users.noreply.github.com`)
- Region: `northeurope`
- GitHub: `samoletovs/foundryLab` (private)

## Getting started

1. Copy `.env.example` to `.env` and fill in values
2. Read [docs/vision.md](./docs/vision.md) for context
3. Pick an agent folder under `agents/`, follow its README

## Related projects

- [agentMode](../agentMode/) — the custom-Azure baseline we're comparing against
- [.github/skills/microsoft-foundry](../.github/skills/microsoft-foundry/SKILL.md) — Foundry deployment skill
