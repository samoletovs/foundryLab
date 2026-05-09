# Lab Memory Agent

> **Status:** 📋 Planned — first agent to build in foundryLab
> **Foundry feature focus:** Knowledge grounding (file search / vector store), retrieval evals, API-callable agent

## What it does

A Foundry-hosted agent that knows the entire NauroLabs lab — its vision, decisions,
project history, killed experiments, plan/ops reports, and commit messages — and
answers questions about it with citations.

### Example questions it should answer

- "Why did we drop X feature in rosette?"
- "What did the last nauro-plan report recommend for golazo?"
- "Which projects depend on data.gov.lv?"
- "What worked in amberRepublic that we should reuse in portaBaltica?"
- "What's our current monetization hypothesis for turgo?"
- "Show me every Azure cost optimization we've ever applied."

### Who calls it

- **Sam (human)** — via Foundry playground or Telegram (later, through agentMode)
- **Other agents** — `nauro-plan` and `nauro-build` consult it for prior context
  before generating new ideas or scaffolds (avoids repeating mistakes / re-discovering
  things we already decided)

## Why it's worth building

1. **Highest Foundry-feature density** — exercises file search, vector store, retrieval evals, structured citations, agent-as-API
2. **Compounding value** — every new report/decision makes it smarter
3. **Vision-aligned** — directly supports the "self-running company" question by giving every other agent institutional memory
4. **Comparable** — the alternative (custom AI Search + Functions + RAG plumbing) is well-understood, so we get a clean Foundry vs. custom comparison

## Knowledge sources to ingest

| Source | Path | Update freq | Notes |
|--------|------|-------------|-------|
| Vision | `.github/VISION.md` | rare | Single source of strategic truth |
| Workspace conventions | `.github/WORKSPACE.md` | rare | |
| Plan reports | `.github/reports/plan/*.md` | weekly | Append-only |
| Ops reports | `.github/reports/ops/*.md` | weekly | Append-only |
| Build reports | `.github/reports/build/*.md` | per-build | If exists |
| Project READMEs | `*/README.md` | low | One per project |
| Project AGENTS.md | `*/AGENTS.md` | low | |
| Vision/blueprint docs | `*/VISION.md`, `*/PROJECT_BLUEPRINT.md` | low | turgo, portaBaltica have these |
| Workspace manifest | `.github/config/workspace-manifest.json` | rare | Source of truth for projects |
| Recent commit messages | `git log --since=...` | daily | Top N most recent across all projects |

**Out of scope (v1):**
- Source code itself (too much noise — start with curated docs)
- Issue/PR history (future enhancement)
- Slack/Telegram conversation logs (privacy, future enhancement)

## Architecture (v1)

```text
                    ┌──────────────────────────┐
                    │  Sam / nauro-plan / etc. │
                    └────────────┬─────────────┘
                                 │ (question)
                                 ▼
                ┌────────────────────────────────┐
                │  labMemoryAgent (Foundry)      │
                │  - prompt: librarian persona   │
                │  - tool: file_search           │
                │  - tool: get_recent_commits    │  ← optional custom tool
                │  - output: answer + citations  │
                └────────────┬───────────────────┘
                             │
                             ▼
                ┌────────────────────────────────┐
                │  Foundry vector store          │
                │  (Azure AI Search backend)     │
                │  populated by ingest pipeline  │
                └────────────────────────────────┘
                             ▲
                             │ (chunks + embeddings)
                ┌────────────┴───────────────────┐
                │  Ingest pipeline (Python)      │
                │  Run weekly (or on demand)     │
                │  - reads sources above         │
                │  - chunks                      │
                │  - uploads to vector store     │
                │  - tags chunks (project, date) │
                └────────────────────────────────┘
```

## Build plan (phased)

### Phase 0 — Provision (couple hours)
- Create resource group `foundrylab-rg` (`northeurope`)
- Create Foundry project `foundrylab`
- Deploy `gpt-4o-mini` model
- Create shared App Insights
- Save endpoint + connection string to `foundryLab/.env`

### Phase 1 — MVP ingestion (one evening)
- Python script `src/ingest.py`:
  - Read curated sources list from `config/sources.yaml`
  - Read each file, chunk (default 800 tokens, 100 overlap)
  - Upload to Foundry vector store with metadata (`project`, `source_path`, `last_modified`)
- Run once manually, verify chunks appear in Foundry portal

### Phase 2 — Agent definition (one evening)
- `agent.yaml` with:
  - Persona: "NauroLabs librarian — answer with citations only, say 'I don't know' if not in sources"
  - Tool: `file_search` bound to the vector store
  - Output schema: `{answer: str, citations: [{source: str, snippet: str}], confidence: "high"|"medium"|"low"}`
- Test in Foundry playground with 10 hand-crafted questions

### Phase 3 — Evaluation (one evening)
- Build dataset of ~20 Q+expected-source pairs in `evals/golden.jsonl`
- Custom evaluators:
  - **Citation correctness** — did it cite at least one source we expect?
  - **Groundedness** — does the answer text overlap meaningfully with cited chunk?
  - **Refusal accuracy** — for unknowable questions, does it correctly say "I don't know"?
- Run batch eval, record baseline scores in `evals/results/baseline.json`

### Phase 4 — Make it callable (one evening)
- Wrap as REST endpoint (Foundry agent invocation)
- Add a small CLI: `python src/ask.py "why did we drop X?"`
- Document how nauro-plan / nauro-build / agentMode can call it

### Phase 5 — Continuous improvement (ongoing)
- Schedule weekly ingest (GitHub Action or Container Apps Job)
- Schedule weekly continuous eval — alert on score regression
- Feed wrong answers back into the eval set
- Try Foundry's prompt optimizer on the librarian prompt; A/B test

## Acceptance criteria for v1

- [ ] Answers 8/10 hand-crafted questions correctly with valid citations
- [ ] Refuses 5/5 out-of-scope questions ("what's the weather?") without hallucinating
- [ ] Ingestion takes < 5 min for full lab corpus
- [ ] Total monthly cost ≤ €3
- [ ] Callable via single Python function from another agent
- [ ] One concrete observation logged in [../../docs/learnings.md](../../docs/learnings.md)

## Folder structure (to be created during build)

```text
labMemoryAgent/
├── README.md                   # this file
├── agent.yaml                  # Foundry agent definition (Phase 2)
├── .env.example                # agent-specific env (if any)
├── config/
│   └── sources.yaml            # what to ingest, with globs and tags
├── src/
│   ├── ingest.py               # ingestion pipeline (Phase 1)
│   ├── ask.py                  # CLI for testing (Phase 4)
│   └── client.py               # reusable client other agents import (Phase 4)
├── evals/
│   ├── golden.jsonl            # Q+expected-source pairs (Phase 3)
│   ├── evaluators.py           # custom Foundry evaluators (Phase 3)
│   └── results/                # eval run outputs (gitignored)
├── infrastructure/
│   ├── main.bicep              # vector store, role assignments
│   └── parameters.json
└── tests/
    └── test_ingest.py          # pytest for ingestion logic
```

## Open questions to resolve during build

- **Chunking strategy** — markdown headings vs. fixed token windows? Test both.
- **Refresh strategy** — full re-ingest weekly, or incremental on git change?
- **Multi-tenancy** — one vector store with `project` metadata filter, or one per project?
- **Privacy** — are any source files private? (`.env.example` only — fine, no secrets)
- **Citation UX** — return source paths or also clickable markdown links?

## Comparison hypotheses to validate

After build, fill in the row in [../../docs/comparison.md](../../docs/comparison.md):

- Foundry RAG setup time vs. building same with Azure AI Search + custom Functions
- Quality difference (eval scores) Foundry default chunking vs. custom
- Real cost vs. the €2–3/mo estimate
- Whether prompt optimizer measurably improves librarian answers

## Next step

Phase 0 (provision Foundry project). Sam to confirm before we start spending.
