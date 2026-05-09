# foundryLab — Agent Guidance

## Project type

Microsoft Foundry experiment lab. Each subfolder under `agents/` is a separate
Foundry agent with its own purpose, deployment, and evaluation suite.

## Where things live

| What | Where |
|------|-------|
| Cross-agent docs (vision, comparison, learnings) | `docs/` |
| Individual agent code | `agents/<agentName>/` |
| Shared Azure infra (Foundry project, App Insights) | `shared/infrastructure/` |
| Shared Python helpers | `shared/lib/` |
| Cross-agent scripts | `scripts/` |

## Coding standards

- **Python 3.11** for all Foundry agent code
- **Bicep** for any Azure resources (no Terraform, no ARM)
- **DefaultAzureCredential** for all Azure SDK access — never API keys
- **Type hints required** in Python code
- **Pytest** for tests, **Foundry evals** for agent quality
- Secrets in `.env` (gitignored), template in `.env.example`

## Cost discipline

- Default model: `gpt-4o-mini`
- Upgrade to `gpt-4o` only if mini fails an eval gate
- No always-on containers — use scheduled jobs or hosted agents on demand
- No Bing Grounding ($35 / 1000 queries) — use direct API calls
- Vector store / file search: only enable if RAG quality demands it

## When working on an agent

1. Read the agent's `README.md` first — it has the plan, schema, and acceptance criteria
2. Check `docs/comparison.md` to see what we've learned about Foundry already
3. Update `docs/learnings.md` after every meaningful insight
4. Update `docs/pricing-notes.md` with actual costs after deployment

## Skills to invoke

- `microsoft-foundry` — for deploying, evaluating, optimizing agents
- `azure-identity-py` — for credential setup
- `azure-monitor-opentelemetry-py` — for observability
- `nauro-ops` — when checking how foundryLab impacts overall lab cost
