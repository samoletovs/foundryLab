# foundryLab

foundryLab is a Microsoft Foundry experiment hub. It builds small, evaluated
agents to compare Foundry with alternatives such as custom Azure agents and
Copilot Studio.

## Research question

foundryLab supports the nauroLabs question **"Can a company run itself?"** by
testing whether a managed agent platform makes the lab's own automation easier
to operate, evaluate, and understand. The practical question is narrower:
**when is Foundry the right tool, and when is it unnecessary platform overhead?**

This is a learning lab, not a product. Each agent exists to answer a specific
question about capability, cost, or developer experience.

## Agent roadmap

| # | Agent | Folder | Status | Goal |
|---|-------|--------|--------|------|
| 1 | Lab Memory Agent | [agents/labMemoryAgent](./agents/labMemoryAgent/) | ✅ P0+P1+P2+P3 done | Test RAG / knowledge grounding |
| 2 | NauroLabs Watcher | _not started_ | — | Test scheduled hosted agents |
| 3 | AgentMode Dataset Curator | _not started_ | — | Test evals + prompt optimizer |
| 4 | Idea Validator | _not started_ | — | Test connected multi-agent |
| 5 | Receipt Processor | _not started_ | — | Test multimodal vision |

See [docs/vision.md](docs/vision.md) for the plan and rationale.

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

## Stack

- Microsoft Foundry (agents + evals + datasets)
- Azure OpenAI (`gpt-4o-mini` default)
- Bicep for any custom Azure resources
- Python 3.11 (Foundry SDK)
- DefaultAzureCredential everywhere — no API keys

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Azure-backed examples require an authenticated Azure CLI session and values in
`.env`. Start with
[agents/labMemoryAgent/README.md](agents/labMemoryAgent/README.md) for the
implemented agent. There is not yet a repository-level automated test suite;
each agent documents its own evaluations and smoke checks.

## Status

**Research.** The lab memory agent has completed its ingestion, provisioning,
and evaluation phases. The other candidate agents are not started. Findings are
recorded in [docs/learnings.md](docs/learnings.md) and
[docs/comparison.md](docs/comparison.md).

## Related projects

- [agentMode](https://github.com/samoletovs/agentMode) - custom Azure baseline

## License

MIT
