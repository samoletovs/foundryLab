# foundryLab — Vision

## What we're trying to learn

Microsoft Foundry is one of several ways to build agentic systems. NauroLabs already
has working alternatives:

- **Custom Azure Functions + Azure OpenAI** (`agentMode/`) — full control, low cost
- **VS Code skills + Copilot agents** (`.github/skills/`) — fast iteration, no deploy
- **Claude Agent SDK** — if/when we use it

The questions we want answered, with evidence:

1. **DX** — Is Foundry faster to build with than custom Functions? At what cost?
2. **Quality** — Do Foundry's evals + prompt optimizer measurably improve agent output?
3. **Observability** — Is Foundry tracing better than App Insights + custom logs?
4. **Cost** — What's the real €/month for a small lab running 5 agents?
5. **Lock-in** — How portable is a Foundry agent? Could we move it back to Functions?
6. **Sweet spot** — Which agent types belong in Foundry vs. custom code vs. skills?

## How we'll answer them

Build 5 agents in priority order. After each, update `docs/comparison.md` and
`docs/learnings.md` with concrete observations.

| Order | Agent | Foundry feature exercised | Question it answers |
|------|-------|---------------------------|---------------------|
| 1 | **Lab Memory Agent** | Knowledge grounding (file search / vector store) | Q1, Q3 — RAG DX & quality |
| 2 | NauroLabs Watcher | Hosted/scheduled agents | Q1, Q4 — scheduled jobs cost & DX |
| 3 | AgentMode Dataset Curator | Evals + prompt optimizer + datasets | Q2 — does Foundry actually improve quality? |
| 4 | Idea Validator | Connected agents | Q1 — multi-agent orchestration DX |
| 5 | Receipt Processor | Multimodal vision | Q1, Q4 — vision cost vs. custom |

By the end, every cell in `docs/comparison.md` should have evidence from a real build.

## Non-goals

- **Not** rewriting agentMode in Foundry (yet — that's a separate decision after we learn)
- **Not** chasing Foundry's full feature surface (skip what doesn't answer our questions)
- **Not** building products to sell from foundryLab — these are experiments

## Success criteria

After ~3 months we should be able to confidently answer:

- "For a new NauroLabs agent X, should we use Foundry or custom code?" — with a decision flowchart
- Total foundryLab Azure spend stayed under €10/month
- At least one Foundry agent demonstrably outperforms its custom-code alternative on a measurable metric

## Vision tie-in

This experiment lives at the intersection of two NauroLabs core questions:

- **"Can a company run itself?"** — Foundry's continuous evals + monitoring may let agents self-improve without our intervention. Evidence here informs the rest of the lab.
- **"Do we still need apps?"** — Foundry pushes hard on agent-as-product. If it's good enough, future projects might skip the React frontend entirely.
