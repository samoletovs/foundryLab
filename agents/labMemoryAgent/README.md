# Lab Memory Agent

> **Status:** ✅ Phase 1 + 2 complete — persistent agent running
> **Foundry feature focus:** Knowledge grounding (file search / vector store), retrieval evals, API-callable agent

## Quick start

From workspace root:

```powershell
# 1. Ensure .venv has deps
.\.venv\Scripts\python.exe -m pip install -r foundryLab\requirements.txt

# 2. (one-time) Ingest sources into Foundry
.\.venv\Scripts\python.exe foundryLab\agents\labMemoryAgent\src\ingest.py

# 3. (one-time) Provision the persistent agent
.\.venv\Scripts\python.exe foundryLab\agents\labMemoryAgent\src\provision.py

# 4. Ask a question
.\.venv\Scripts\python.exe foundryLab\agents\labMemoryAgent\src\ask.py "Why does foundryLab exist?"

# JSON output (for scripts/agents)
.\.venv\Scripts\python.exe foundryLab\agents\labMemoryAgent\src\ask.py --json "What is rosette?"
```

To **refresh** the corpus after editing docs/reports: re-run `ingest.py` (it
deletes & rebuilds the vector store) then re-run `provision.py` (it updates
the agent to point at the new store, same name same agent_id).

## Files

| Path | Purpose |
|------|---------|
| [config/sources.yaml](config/sources.yaml) | Declares which files to ingest (10 source groups, 56 files) |
| [config/ingest-state.json](config/ingest-state.json) | Vector store ID + per-file mapping (gitignored output) |
| [config/agent-state.json](config/agent-state.json) | Persistent agent ID (gitignored output) |
| [src/config.py](src/config.py) | Constants: agent name, persona, paths, env loading |
| [src/ingest.py](src/ingest.py) | Phase 1: upload files, create vector store |
| [src/provision.py](src/provision.py) | Phase 2: create/update the persistent agent |
| [src/client.py](src/client.py) | Reusable `ask(question)` API for other tools |
| [src/ask.py](src/ask.py) | CLI wrapper |
| [src/verify.py](src/verify.py) | Diagnostic listing of vector stores + files |
| [src/smoke_test.py](src/smoke_test.py) | Throwaway-agent smoke test (Phase 1 acceptance) |

## Architecture

```text
            ┌────────────────────────────┐
            │  CLI / nauro-plan / agent  │
            └─────────────┬──────────────┘
                          │ ask("question")
                          ▼
            ┌────────────────────────────┐
            │  client.py — ask()         │
            │  - thread per call         │
            │  - extract citations       │
            └─────────────┬──────────────┘
                          │
                          ▼
            ┌────────────────────────────┐
            │  Foundry agent: lab-memory │
            │  - gpt-4o-mini             │
            │  - file_search tool        │
            │  - librarian persona       │
            └─────────────┬──────────────┘
                          │
                          ▼
            ┌────────────────────────────┐
            │  Vector store: lab-memory  │
            │  - 56 files, 689 KB        │
            │  - Foundry-managed embeds  │
            └────────────────────────────┘
                          ▲
                          │ ingest.py uploads
            ┌────────────────────────────┐
            │  Local source files        │
            │  - .github/VISION.md, etc. │
            │  - reports/, READMEs       │
            └────────────────────────────┘
```

## Acceptance criteria

- [x] Answers grounded questions correctly with valid citations (3/3 in smoke)
- [x] Refuses out-of-scope questions cleanly ("I don't know")
- [x] Ingestion takes < 5 min for full lab corpus
- [x] Total monthly cost ≤ €3 (currently <€0.05 cumulative)
- [x] Callable via single Python function from another agent (`client.ask`)
- [ ] Phase 3: scheduled re-ingest + Foundry continuous eval — not started

## Knowledge sources currently ingested

10 groups, 56 files total:

| Group | Files | Notes |
|-------|-------|-------|
| vision | 1 | `.github/VISION.md` |
| workspace-conventions | 1 | `.github/WORKSPACE.md` |
| workspace-manifest | 1 | project registry |
| plan-reports | 9 | `nauro-plan` outputs |
| ops-reports | 9 | `nauro-ops` outputs |
| run-reports | 10 | `nauro-run` outputs |
| build-reports | 0 | none yet |
| project-readmes | 9 | one per project |
| project-agents-md | 9 | per-project AI guidance |
| project-visions | 4 | golazo, portaBaltica, tPlan, foundryLab |
| foundrylab-learnings | 3 | this lab's own docs |

## Open questions to resolve later

- **Refresh strategy** — full re-ingest is fine for 56 files, but at 500+
  files we'll want incremental (compare file checksum vs. last ingest)
- **Citation UX** — currently filenames; could enrich to clickable repo URLs
- **Multi-tenancy** — single store with metadata tags, or separate stores
  per project? Single is simpler; revisit if cross-project leakage hurts
  retrieval
- **Continuous eval** — Phase 3: define golden dataset and use Foundry's
  `continuous_eval_create` to alert on regressions

## What this taught us about Foundry

See [../../docs/learnings.md](../../docs/learnings.md) for full notes. The
short version: **Foundry's Basic agent setup eliminates RAG plumbing**.
We wrote zero chunking/embedding/vector-DB code; in exchange we accept
MS-managed storage and embeddings, which is fine for non-confidential lab data.
