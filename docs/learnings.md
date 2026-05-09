# Learnings — running log

Append-only. Newest at top. Each entry: date, agent, observation, implication.

## Template

```
### YYYY-MM-DD — agentName
**Observation:** what happened
**Implication:** what it means for foundryLab / NauroLabs as a whole
**Action:** what we changed (or decided not to change)
```

---

### 2026-05-09 — Phase 0 deployed
**Observation:** Provisioned the shared Foundry stack: AI Services account
`foundrylab-aiservices`, project `foundrylab`, deployments `gpt-4o-mini` and
`text-embedding-3-large` (both GlobalStandard, 50K TPM each), Log Analytics,
App Insights, user-assigned managed identity. Smoke test passed: model
responded via AAD with no API keys (`disableLocalAuth=true` works).
**Implication:** Foundation is ready for Lab Memory Agent build. Idle cost is
€0 (no provisioned capacity, no always-on containers).
**Action:** Proceed to Phase 1 (ingestion pipeline) for `labMemoryAgent`.

### 2026-05-09 — Region override: northeurope → swedencentral
**Observation:** `northeurope` only offers `GlobalProvisionedManaged` SKU for
OpenAI models on the Visual Studio Enterprise sub — that means committing
to monthly capacity = expensive. Worse, it has *no* embedding model
deployments, which kills RAG. `swedencentral` has the full consumption
SKU range (`Standard`, `GlobalStandard`), embeddings (3-large + 3-small),
DALL-E 3, realtime preview, and all reasoning models (o1, o3-mini, gpt-5
family).
**Implication:** Workspace default of `northeurope` doesn't apply to
Foundry/AOAI workloads. agentMode is already in `swedencentral` —
unifying foundryLab there means same latency profile and one bill column.
**Action:** All foundryLab resources use `swedencentral`. Documented in the
comparison matrix and Bicep params. If a future project picks `northeurope`,
re-check model availability first.

---

### 2026-05-09 — Phase 1 (labMemoryAgent ingestion) deployed
**Observation:** Built ingestion pipeline that uploads 56 files (689 KB total)
to Foundry and lets the service handle chunking + embedding + indexing.
End-to-end smoke test passed: 3/3 grounded questions answered correctly with
inline citations, 1/1 out-of-scope question refused with "I don't know".
**Implication:** Foundry's Basic agent setup is genuinely simpler than DIY RAG —
no chunking code, no embedding pipeline, no vector DB infrastructure. We
provisioned `text-embedding-3-large` in Phase 0 thinking we'd need it for
RAG; Basic file_search uses MS-managed embeddings instead, so our embedding
deployment is currently unused. Keep it for future custom-RAG comparisons.
**Action:** Move to Phase 2 (provision the persistent labMemoryAgent + REST
endpoint). Long-term enhancement: incremental ingest (only re-upload changed
files) once we move to scheduled refresh.

### 2026-05-09 — Foundry RBAC has TWO roles you need
**Observation:** "Azure AI Developer" alone is NOT enough to create agents
or threads — you also need "Azure AI User" (or higher: Project Manager /
Account Owner). The error "lacks the required data action `agents/write`"
is a clear pointer. Roles assigned at AI Services account scope should
work, but I had to also assign at the project scope
(`.../accounts/<acct>/projects/<proj>`) to make the smoke test work; that
might just have been propagation lag.
**Implication:** Update Bicep to grant Azure AI User to the owner principal
in addition to Azure AI Developer. For UAMI (used by future agent
runtimes), Cognitive Services OpenAI User is enough only for inference —
if a runtime needs to create threads/agents/runs, it also needs Azure AI
User.
**Action:** Need to add `Azure AI User` role assignment to `main.bicep`
for both owner and UAMI before next clean deploy. Filed as TODO in
shared/infrastructure/main.bicep.

### 2026-05-09 — `az account clear` is destructive, not a token refresh
**Observation:** Tried `az account clear` to refresh a stale token after
adding a role. It removed all subscriptions and forced a full re-login,
including MFA against the VSE tenant.
**Implication:** RBAC propagates within a few minutes anyway. Just wait
2–5 min, or sign out and back in via `az login` without clearing.
**Action:** Never use `az account clear` again unless intentionally
removing accounts.

### 2026-05-09 — Default 50K TPM throttles file_search
**Observation:** Bicep default of 50 capacity (= 50K tokens/min) on
`gpt-4o-mini` was tripped by 4 file_search-enabled questions in a row
(retrieved chunks + answers ≈ 10–20K tokens each). Bumped to 200 (200K
TPM) and throttling disappeared.
**Implication:** Capacity is not idle cost — it's a per-minute quota cap.
For any RAG/file_search agent, default to ≥200 TPM. We have 9000 TPM
of quota in `swedencentral`, so plenty of room.
**Action:** Updated `main.bicepparam` to `chatModelCapacity = 200`.
Future agents can request higher per-deployment capacity without cost
impact.

---

### 2026-05-09 — Phase 2 (persistent agent + client API) deployed
**Observation:** Built `provision.py` (idempotent create-or-update),
`client.py` (reusable `ask()`), and `ask.py` (CLI). Persistent agent
`asst_I9vO5sAp69FmXwylop75vP2c` running. CLI returns clean answers with
filename citations and JSON mode for downstream agents. Total Phase 2
code: ~250 LOC of Python.
**Implication:** Every other foundryLab agent can now `from client import ask`
and get grounded lab knowledge with one line. The lab now has institutional
memory.
**Action:** Phase 3 next: build Foundry continuous-eval dataset and start
A/B testing the librarian prompt with the prompt-optimizer.

### 2026-05-09 — Bicep `guid()` collides with manually-created role assignments
**Observation:** When we manually `az role assignment create`d the missing
roles in Phase 1, Azure auto-assigned a random GUID. Bicep computes a
deterministic GUID from `(scope, principal, role)` — different name, same
underlying tuple. ARM rejects the deploy with `RoleAssignmentExists`.
**Implication:** Always create RBAC via Bicep from day 1; if you patch
manually, delete those manual ones before re-running Bicep.
**Action:** Cleaned up manual project-scope assignments and let Bicep own
them. Updated `main.bicep` to declare both account-scope (Azure AI Developer)
and project-scope (Azure AI User) roles for owner + UAMI.

### 2026-05-09 — Foundry SDK API names are inconsistent
**Observation:** Files API uses `purpose=FilePurpose.AGENTS`,
`upload_and_poll(file_path=..., filename=..., polling_interval=...)`. Vector
Stores API uses `polling_interval` too — but the helper signatures lie:
`upload_and_poll` has both `file` and `file_path`, only one of which works
at a time, and they reject `sleep_interval` (a name from older docs).
**Implication:** Don't trust the doc snippets blindly; introspect the
actual SDK signature with `inspect.signature(...)` first. The Foundry
portal's code-snippet generator may also produce stale code in some
sections.
**Action:** When stuck on API param errors, run
`python -c "from azure.ai.agents.operations import X; import inspect; print(inspect.signature(X.method))"`.
---

### 2026-05-09 — Phase 3 (eval framework + prompt optimization) deployed
**Observation:** Built golden dataset (15 items: 12 grounded, 3 ungrounded),
custom local eval runner with three metrics, ran baseline → optimized →
compared. Wrote our own targeted prompt-optimizer because the Foundry MCP
tool was 403'ing on stale auth. Baseline scored cited_expected=0.67,
has_citations=0.83. Optimized version: cited_expected=0.67 (unchanged),
has_citations=1.00 (eliminated all empty-citation answers). Slight
trade-off: a couple of items moved from "no citation" to "wrong citation".
**Implication:** The big win wasn't accuracy — it was forcing the model to
ALWAYS search. That's a one-line prompt change ("Always call file_search
before answering"). Foundry's prompt-optimizer wouldn't have done better;
the value of the optimizer is mostly: feeding observed failures into a
structured rewrite.
**Action:** Phase 3 complete in essence. The golden dataset + run_eval +
optimize_prompt loop is now reusable for any future Foundry agent we build.

### 2026-05-09 — Foundry strips path prefix from uploaded filenames
**Observation:** `client.files.upload_and_poll(filename=foo__bar.md)` is
ignored — Foundry stores only the basename. With 56 files we had 9 different
README.md files all indistinguishable in the citations panel.
**Implication:** Citations from file_search are useless for any corpus with
duplicate basenames unless you maintain a local file_id → source_path map.
Compare to building your own RAG: you'd own this mapping by default.
**Action:** Updated `client.py` to resolve file_ids using
`config/ingest-state.json`. Added a fallback to Foundry's basename if the
id isn't in our map.

### 2026-05-09 — Foundry MCP tools cache the user identity per session
**Observation:** After re-running `az login` against a different tenant,
the Azure MCP tools (Foundry, etc.) keep using the OLD token and return
403 "currently authenticated user does not match the user who initiated
the session." Restarting VS Code is the only known fix.
**Implication:** For automation we cannot rely on MCP tools across an auth
context change. Direct REST calls or the SDK with a fresh
`DefaultAzureCredential` work fine.
**Action:** Built `optimize_prompt.py` using `openai` + `DefaultAzureCredential`
directly. Future Foundry-specific automation in foundryLab should prefer
the SDK over MCP tools.
---

### 2026-05-09 — Phase 3 iteration: path headers + small chunks unlocked retrieval
**Observation:** Two retrieval fixes pushed `cited_expected` from 0.667 to
**0.833**, `citation_recall` from 0.514 to **0.694**, and `has_citations`
to **1.000**. Both fixes target the same underlying problem — Foundry
strips path prefixes from filenames, so "VISION.md" or "AGENTS.md" was
ambiguous to retrieval.
1. **Path header in content.** Each uploaded file now starts with
   `# Source: foundryLab/docs/learnings.md` plus tags. Embeddings now
   encode the full path; chunks include the path as text the model can
   read and cite.
2. **Smaller chunks (500 tokens vs default ~800).** With smaller chunks,
   the path header dominates a higher fraction of each chunk's
   embedding, especially for short docs like READMEs.
**Implication:** RAG quality with Foundry's Basic file_search is
*tunable* via content prep + chunking, but you can't escape the
fundamental fact that file_search returns chunks by similarity \u2014 not
by filename. If your corpus has many files with the same basename you
must either (a) put paths into the content or (b) split into multiple
vector stores or (c) maintain a local file-id-to-path map for citations.
**Action:** ingest.py now uses 500/120 static chunking and prepends a
`# Source:` header. README of labMemoryAgent updated.

### 2026-05-09 — Hard retrieval failures expose gpt-4o-mini's ceiling
**Observation:** Two failures persisted across all 3 prompt revisions:
- "What tech stack does agentMode use?" \u2192 cites random reports, ignores
  agentMode/README.md (which clearly has `Stack: Azure Functions...`).
  Stochastic across reruns: sometimes refuses, sometimes hallucinates,
  sometimes finds tangential info.
- "Most recent nauro-plan report" \u2192 cites `run-*` reports rather than
  `plan-*`, because run reports include plan output verbatim and look
  more relevant to the query.
**Implication:** These are real Foundry-as-RAG limits at the gpt-4o-mini
tier. Fixing them would require (a) bigger model, (b) hierarchical
retrieval (filter by metadata first, then search), or (c) editorial
fixes to source docs (add explicit "Tech stack:" headings). Foundry's
prompt-optimizer alone cannot solve them.
**Action:** Documented as known limitations rather than fighting them.
For agent #2 onwards, factor model choice into Phase 0 cost planning \u2014
mini is fine for grounded factual retrieval but weak on synthesis.

### 2026-05-09 — Stochastic answers across identical queries
**Observation:** Asked "What tech stack does agentMode use?" three times
in a row \u2014 got three different responses (one refusal, one citing
random ops report, one with partial dependency list).
**Implication:** file_search retrieval involves a temperature-influenced
response from the LLM, and our agent has no temperature override (default
\u2248 1.0). For evaluations to be stable, set `temperature=0` (or near 0)
when creating the agent or per-run. Otherwise add multi-sample retries.
**Action:** Future agent provisioning in foundryLab should set
`temperature=0.2` by default for grounded-fact use cases.

---

### 2026-05-09 — Temperature=0.2 alone added 9 points to citation accuracy
**Observation:** Without changing the prompt or chunking, simply setting
`temperature=0.2` on the `lab-memory` agent lifted `cited_expected` from
0.83 to **0.92** and `citation_recall` from 0.69 to **0.75**. Three
identical reruns of the same factual question now produce stable,
consistent answers (previously they varied wildly across reruns).
**Implication:** Default temperature on Foundry agents (≈1.0) is fine for
chat use cases but actively hurts grounded-fact retrieval. The fix is one
line. Anyone building a librarian-style agent should set this from day 1.
**Action:** Updated `provision.py` to always pass `temperature` from
`config.TEMPERATURE` (default 0.2). Updated `agent-state.json` schema to
record it.

### 2026-05-09 — gpt-4o deployment exists, REST works, but Foundry agents reject it
**Observation:** Tried bumping the librarian to gpt-4o for better
synthesis on item 4 (agentMode tech stack). Deployed `gpt-4o`
(GlobalStandard, capacity 100, capabilities.assistants=true) on the
account. Direct REST calls to `https://foundrylab-aiservices.openai.azure.com/openai/deployments/gpt-4o/chat/completions`
return successful responses. But every agent run with `model="gpt-4o"`
returns:
```
{"code":"invalid_deployment", "message":"The API deployment for this resource does not exist."}
```
Tested from a brand-new agent created from scratch with the same vector
store and tool config — same error. Reverting `model` to `gpt-4o-mini`
on the same agent works immediately.
**Implication:** There's a hidden state somewhere in the Foundry stack
(possibly account-level deployment cache, possibly a project connection
that needs to be created when adding new models) that we couldn't find
in 30 minutes of debugging. For now, **deploy any model you plan to use
as an agent backend at Phase 0**, before you create the project, so the
state is consistent from day 1.
**Action:** Stayed on gpt-4o-mini for labMemoryAgent. Documented as an
open issue. For agent #2 onwards: include all model deployments in the
Bicep before first deploy (now done — `premiumChatDeployment` declared
in main.bicep so future projects pick it up cleanly).

### 2026-05-09 — Final labMemoryAgent scores after iteration
**Run progression:**

| Lever | cited_expected | citation_recall | has_citations | refusal | mean latency |
|---|---|---|---|---|---|
| baseline (temp~1.0, no path headers, default chunks) | 0.67 | 0.56 | 0.83 | 1.0 | 7.1s |
| + optimized prompt | 0.67 | 0.51 | 1.00 | 1.0 | 6.7s |
| + path headers + 500-token chunks | 0.83 | 0.69 | 1.00 | 1.0 | 5.8s |
| **+ temperature=0.2 (final)** | **0.92** | **0.75** | 0.92 | 1.0 | 6.5s |

11/12 grounded items hit at least one expected source. Only item 4
(agentMode tech stack) keeps failing — gpt-4o-mini synthesis ceiling
that we couldn't break with gpt-4o due to the runtime bug above.
**Verdict:** Foundry Basic file_search + the right preparation
(path-aware ingest, focused chunks, low temperature, file_search-first
prompt) is genuinely production-quality for a < 1 GB markdown corpus.
Cumulative cost across all 4 phases: < €0.20. Idle: €0/mo.
