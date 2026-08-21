# Agent Development with Microsoft Foundry

> **A worked-example walkthrough for a D365 consultant**, grounded in the
> `lab-memory` agent we built end-to-end on May 9, 2026.
>
> Read time: ~30 minutes. Built to be re-read in chunks.

---

## How this guide is structured

Software documentation is best when it doesn't try to do four jobs at once. The
[Diátaxis framework](https://docs.divio.com/documentation-system/) names them:
**tutorial**, **how-to**, **reference**, **explanation**. This guide is mostly
explanation built around a single **worked example**: the actual agent we shipped.

Cognitive-load research is also clear: when learning a new technical domain, you
absorb concepts faster from one fully worked example than from a flood of generic
principles. So every section follows the same pattern:

1. **In our agent** — what we did, with file paths and code
2. **What's actually happening** — the underlying concept, generalized
3. **For a customer build** — how a D365 / Microsoft customer engagement would adapt it

If something doesn't make sense, jump back to the **In our agent** part of that
section — the concrete is the anchor.

> **Where the code lives:** all paths in this guide are relative to the
> [foundryLab/](../) folder. The agent itself is in
> [agents/labMemoryAgent/](../agents/labMemoryAgent/) and shared infra is in
> [shared/infrastructure/](../shared/infrastructure/).

---

## Part 1 — The agent we built, at a glance

NauroLabs has 5 active project folders, plus weekly *plan* and *ops* reports
written by AI agents that scan the workspace, plus vision docs and per-project
READMEs. About 56 markdown files, ~700 KB. The maintainer used to read them by hand to
remember what was decided last week.

We built **`lab-memory`** — a Microsoft Foundry agent that:

- Has all 56 files indexed in a Foundry-managed vector store
- Answers questions like *"why did we drop X feature in rosette?"* with the
  source file cited
- Refuses cleanly when asked things outside the corpus
- Costs **€0/month idle**, ~€0.005 per question, ~€0.05 per evaluation cycle
- Reaches **0.92 cited_expected / 0.75 citation_recall / 1.0 refusal_accuracy**
  on a 15-question golden test

What you'd see using it:

```text
$ python ask.py "What region is foundryLab deployed in and why?"

foundryLab is deployed in Sweden Central. Northeurope was rejected because
it only offered GlobalProvisionedManaged SKUs (committed monthly capacity)
for OpenAI models on the Visual Studio Enterprise subscription, and had no
embedding models available — both of which are blockers for cost-effective
agent development.

Sources:
  - foundryLab/docs/learnings.md
```

That is the entire customer value: cited, grounded, refusing-when-unknown answers
over a private document corpus. Most "AI agent" customer engagements you'll be
asked to deliver in 2026 are variations of exactly this pattern — over an FDD
library, an issue register, a service knowledge base, or a contract repository.

### What it's made of

```
foundryLab/
├── shared/infrastructure/
│   ├── main.bicep                      ← provisions Azure side (Phase 0)
│   ├── main.bicepparam
│   └── deploy.ps1                      ← one-line deploy + .env writer
├── agents/labMemoryAgent/
│   ├── config/
│   │   ├── sources.yaml                ← which local files to ingest
│   │   ├── ingest-state.json           ← (gitignored) file_id → source_path map
│   │   └── agent-state.json            ← (gitignored) persistent agent ID
│   ├── src/
│   │   ├── config.py                   ← persona, paths, env, model name
│   │   ├── ingest.py                   ← uploads files + builds vector store
│   │   ├── provision.py                ← creates / updates the agent
│   │   ├── client.py                   ← reusable ask() function for other tools
│   │   └── ask.py                      ← CLI for humans
│   └── evals/
│       ├── golden.jsonl                ← 15 question + expected-source pairs
│       ├── run_eval.py                 ← runs agent against golden, scores
│       ├── optimize_prompt.py          ← LLM-rewrites the prompt from failures
│       └── results/                    ← versioned scoreboard runs
└── docs/
    ├── vision.md  comparison.md  learnings.md  pricing-notes.md
    └── learning-guide.md               ← this file
```

A consultant takeaway: **this is roughly the file inventory for any production
Foundry agent.** Provisioning Bicep, an ingest script, a provision script, a
reusable client, a CLI, an eval set, and per-eval results. Steal the layout for
customer projects.

---

## Part 2 — The mental model (Foundry concepts via D365 analogies)

Microsoft Foundry has its own hierarchy. Get this right and most other things follow.

```
Azure Subscription
  └── Resource Group                     ← billing / lifecycle boundary
       └── Azure AI Services account     ← "the Foundry account" (kind=AIServices)
            ├── Project                  ← logical workspace, like a Dataverse env
            │    ├── Agent               ← the configured assistant
            │    ├── Vector store(s)     ← knowledge attached to the agent
            │    ├── Files               ← uploaded source documents
            │    ├── Connections         ← link to AI Search / Blob / others
            │    └── Evaluations / Datasets
            └── Model deployments        ← the LLM brains, attached to the account
                 ├── gpt-4o-mini
                 ├── gpt-4o
                 └── text-embedding-3-large
```

Two non-obvious things to remember:

1. **Model deployments live on the *account*, not the project.** One deployment
   serves many projects.
2. **The "Foundry project endpoint"**
   (`https://{account}.services.ai.azure.com/api/projects/{project}`) is the
   address your code talks to. Save it. You'll use it everywhere.

### The seven nouns you must know

| Foundry concept | What it is | D365 analogy |
|---|---|---|
| **Account** | Azure resource owning model deployments and projects | Power Platform tenant |
| **Project** | Workspace for a particular agent or set of agents | Dataverse environment |
| **Model deployment** | A specific OpenAI model provisioned for use | Deployed package version |
| **Agent** | A configured assistant: model + instructions + tools | A custom workflow |
| **Tool** | Something the agent can call (file_search, code_interpreter, custom function) | Action in a workflow |
| **Vector store** | Foundry's managed RAG layer — files + chunks + embeddings | Dataverse search but vectorized |
| **Run** | One execution of the agent against a thread of messages | A workflow run |

If you remember nothing else: **agent = (model + instructions + tools + memory)**.
Every Foundry configuration page is just one of those four nouns.

---

## Part 3 — Walkthrough: what each concept looked like in our code

This is the worked example. For each Foundry concept, we go:

> **In our agent** → **What's actually happening** → **For a customer build**

### 3.1 Provisioning the Foundry account, project, and models

#### In our agent

[`shared/infrastructure/main.bicep`](../shared/infrastructure/main.bicep) declares:

```bicep
// 1. The "Foundry account" — kind=AIServices
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: '${projectKey}-aiservices'   // foundrylab-aiservices
  kind: 'AIServices'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: '${projectKey}-aiservices'
    disableLocalAuth: true            // no API keys — AAD only
    allowProjectManagement: true
  }
}

// 2. A project under it
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServices
  name: 'foundrylab'
  ...
}

// 3. Each model deployment is a child of the account
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: 'gpt-4o-mini'
  sku: { name: 'GlobalStandard'; capacity: 200 }
  properties: { model: { format: 'OpenAI'; name: 'gpt-4o-mini'; version: '2024-07-18' } }
}
```

Plus Log Analytics, App Insights, a user-assigned managed identity, and two
role assignments (`Azure AI Developer` for management, `Azure AI User` for
data-plane). One Bicep file deploys it all.

[`deploy.ps1`](../shared/infrastructure/deploy.ps1) wraps `az deployment group
create` with a preflight check, what-if dry run, and writes outputs to
`foundryLab/.env`.

#### What's actually happening

You are creating three nested Azure resources:
- the **account** is the security and billing boundary
- the **project** is the workspace that holds agents and their state
- the **deployments** are the actual LLM endpoints; they live at the account
  level so multiple projects can share them

`disableLocalAuth=true` is the security default — every call to the account or
project requires an Azure AD token (managed identity in production, your CLI
token in dev). No keys to steal, no keys to rotate.

`GlobalStandard` SKU with `capacity` is *pay-per-token, with a per-minute rate
limit*. There's no idle cost regardless of capacity. We accidentally proved this
by deploying both `gpt-4o-mini` (200K TPM) and `gpt-4o` (100K TPM) — €0/month
idle. The capacity number is a throttle ceiling, not a commitment.

#### For a customer build

| Customer scenario | Recommended approach |
|---|---|
| Pilot / POC | Single `S0` account, single project, `gpt-4o-mini` only. Hard-cap capacity at e.g. 100K TPM until usage data exists. |
| Multi-business-unit | One account, one project per business unit. RBAC at the project scope keeps data plane isolated. |
| Regulated / data residency | Use Foundry **Standard setup** (your own AI Search and Blob Storage), or pin all resources to a specific region with a private endpoint. |
| Production rollout | Bicep + `azd` for the lifecycle. Diagnostic settings on day 1. Budget alerts at the resource group. |

**Customer cost framing:** "Idle Foundry costs €0. You'll pay only when employees
ask the agent something." That sentence reframes most pilot conversations.

---

### 3.2 Knowledge ingestion — building the vector store

#### In our agent

[`agents/labMemoryAgent/src/ingest.py`](../agents/labMemoryAgent/src/ingest.py)
does this:

```python
# 1. Read declarative source list with globs
sources = load_sources()   # parses config/sources.yaml

# 2. For each source file, prepend a header so paths survive
for src in sources:
    header = f"# Source: {src.relative_path}\n# Tags: ...\n\n"
    payload = header.encode("utf-8") + src.path.read_bytes()
    result = client.files.upload_and_poll(
        file=(safe_name, payload),
        purpose=FilePurpose.AGENTS,
    )
    file_ids.append(result.id)

# 3. Build the vector store from those files
store = client.vector_stores.create_and_poll(
    file_ids=file_ids,
    name="lab-memory",
    chunking_strategy=VectorStoreStaticChunkingStrategyRequest(
        static=VectorStoreStaticChunkingStrategyOptions(
            max_chunk_size_tokens=500,
            chunk_overlap_tokens=120,
        ),
    ),
)
```

That is the whole RAG pipeline. **No embedding code. No vector DB. No retrieval
client. Foundry handles all of it.**

[`config/sources.yaml`](../agents/labMemoryAgent/config/sources.yaml) is the
declarative inventory of what gets ingested:

```yaml
sources:
  - name: vision
    paths: [".github/VISION.md"]
    tags: { category: vision, scope: lab }
  - name: plan-reports
    paths: [".github/reports/plan/*.md"]
    tags: { category: report, scope: lab, agent: nauro-plan }
  - name: project-readmes
    paths: ["agentMode/README.md", "amberRepublic/README.md", ...]
    tags: { category: readme, scope: project }
```

#### What's actually happening

A "vector store" in Foundry is *literally* a managed Azure AI Search index
populated from the files you upload. Foundry parses each file, splits it into
chunks (you can control how), embeds each chunk into a 1,536- or 3,072-dimension
vector, and indexes them.

When the agent later runs `file_search`, Foundry:
1. Embeds the user's question into the same vector space
2. Pulls the top-N most similar chunks (cosine similarity)
3. Stuffs them into the model's context, with citation annotations

Two design choices matter a lot:

**Path-aware ingestion.** Foundry strips path prefixes — uploading
`agentMode/AGENTS.md` and `rosette/AGENTS.md` gives you two files both named
`AGENTS.md` with no way to tell them apart in citations. Our fix: prepend a
`# Source: <path>` header into the file content before upload. This lifts
`cited_expected` from 0.67 to 0.83 in our evals.

**Chunk size.** Default is ~800 tokens. We set `max_chunk_size_tokens=500` /
`chunk_overlap_tokens=120` so the path header dominates a higher fraction of
each chunk's embedding. This was an extra +3 percentage points.

#### For a customer build

The replacement work is replacing `sources.yaml` with whatever the customer's
private corpus actually is.

| Customer corpus | Ingestion approach |
|---|---|
| SharePoint library | Use Microsoft Graph to enumerate documents, download to local cache, run our `ingest.py` pattern unchanged |
| Confluence space | Confluence REST API export → markdown via `pandoc` → ingest |
| D365 attached docs | Dataverse Web API to enumerate, then `Microsoft.CRM.SDK.Document` download → ingest |
| FDDs / SOWs in Word/PDF | Foundry accepts PDF and Word natively; you can skip the markdown step |
| Service desk KB articles | Most ITSM tools have a REST export; iterate, write to local, ingest |

**Common considerations:**
- **Re-ingest cadence.** Our agent does full re-ingest every time `ingest.py`
  runs. Fine for ~700 KB. For >100 MB or >1000 files, build incremental ingest
  by checking last-modified vs. `ingest-state.json`.
- **Sensitive data.** If the corpus contains PII, regulated finance data, or
  customer-confidential content, switch to **Foundry Standard setup**: your own
  Azure AI Search + Blob Storage, both with private endpoints. The agent code
  is identical; only the connection backend changes.
- **Refresh strategy with deletions.** When a source doc is deleted, the chunks
  must be removed from the vector store too. Easiest: full delete-and-rebuild
  (what we do). For larger corpora: tag chunks with the source path on ingest,
  re-ingest by source path on changes.

---

### 3.3 The agent itself — six lines that define behavior

#### In our agent

[`agents/labMemoryAgent/src/provision.py`](../agents/labMemoryAgent/src/provision.py):

```python
file_search = FileSearchTool(vector_store_ids=[vector_store_id])

agent = client.create_agent(
    model="gpt-4o-mini",                 # which LLM is the brain
    name="lab-memory",                   # stable name → idempotent updates
    instructions=INSTRUCTIONS,           # the system prompt / persona
    tools=file_search.definitions,       # what tools it can call
    tool_resources=file_search.resources,
    temperature=0.2,                     # how deterministic the answers are
)
```

[`config.py`](../agents/labMemoryAgent/src/config.py) holds the `INSTRUCTIONS`
string — about 300 words telling the model:

- It's the NauroLabs librarian
- Always call `file_search` before answering grounded questions
- Cite the most specific source path
- Refuse with the exact phrase *"I don't know — that's not in the lab documents."*
  for ungrounded questions
- Recognize report folder conventions

#### What's actually happening

Every Foundry agent is **configuration**, not code. The "agent" is a JSON
record in the project saying: when someone sends me a message, use this model,
follow these instructions, and you may use these tools.

Three knobs we tuned, in order of impact:

1. **`temperature=0.2`** was the single biggest win. The default ~1.0 gives
   chatty, stochastic answers — same question three times produced three
   different answers, sometimes citing nothing. At 0.2 the agent sticks to
   what it retrieved. **+9 percentage points** of citation accuracy.
2. **`instructions`** is the system prompt; we iterated it twice based on
   observed failures. The version that won says explicitly: *"Always call
   file_search before answering any grounded question."* That alone moved
   `has_citations` from 0.83 to 1.00.
3. **`tools=file_search.definitions`** is the list of capabilities. Other
   options:
   - `CodeInterpreterTool` — runs Python in a sandbox; great for data analysis
   - `FunctionTool(name="get_invoice_by_id", ...)` — calls a user-defined
     Python function
   - Bing/Web search — costs $35/1000 queries; use sparingly
   - Connected agents — invoke another agent as a tool

#### For a customer build

The instructions block is where domain expertise goes. Some customer-specific
patterns:

| Scenario | Custom instruction snippet to add |
|---|---|
| Tax determination explainer | *"Always cite the specific tax code, jurisdiction, and rule version. If multiple rules could apply, list them all and note the most specific."* |
| AP posting profile copilot | *"When the user gives an invoice number, always look it up in the file_search before commenting. Never invent posting accounts."* |
| Service desk triage | *"Categorize each request into one of: incident / service request / question. If unsure, ask one clarifying question; never categorize without explicit information."* |
| Contract review | *"Cite the clause number for every claim. If the user asks for a recommendation, mark it clearly as 'guidance, not legal advice'."* |

**The `temperature=0.2` rule applies to virtually every customer use case.**
Anyone building a grounded-fact agent should default to 0.2. Use 0.7+ only for
creative tasks (drafting marketing copy, generating ideas).

---

### 3.4 Calling the agent — threads, runs, citations

#### In our agent

[`agents/labMemoryAgent/src/client.py`](../agents/labMemoryAgent/src/client.py):

```python
def ask(question: str) -> AskResult:
    client, agent_id, file_id_to_path = _ensure_initialized()

    # 1. A thread is a conversation container
    thread = client.threads.create()

    # 2. Add the user's message to it
    client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=question,
    )

    # 3. Run the agent against the thread; SDK polls until done
    run = client.runs.create_and_process(
        thread_id=thread.id,
        agent_id=agent_id,
    )

    # 4. Read the most recent agent message + extract citations
    msgs = list(client.messages.list(thread_id=thread.id, ...))
    agent_msg = next(m for m in reversed(msgs) if m.role == MessageRole.AGENT)
    answer, file_ids = _extract_answer_and_citations(agent_msg)

    # 5. Resolve file_ids to original source paths
    citations = [file_id_to_path.get(fid, "<unknown>") for fid in file_ids]

    return AskResult(answer=answer, citations=citations, ...)
```

[`ask.py`](../agents/labMemoryAgent/src/ask.py) wraps that as a CLI;
`client.ask()` is what other Python code (or another agent) imports.

#### What's actually happening

Three Foundry primitives at play:

- **Thread** — an ordered list of messages between user and agent. Persistent.
  You can have 1000 threads per project.
- **Message** — a user or agent turn within a thread. Includes optional
  attachments.
- **Run** — *one execution of the agent against a thread*. The model decides
  whether to call tools, consults retrieval, generates a response, and writes
  it back as a new message. `create_and_process` is the SDK's polling helper.

A nice property: threads are stateful so you can build multi-turn dialogue by
keeping the same `thread_id` across calls. We don't need that for the librarian,
so we delete the thread after each question.

The citation extraction is the only fiddly bit. Foundry annotates the answer
text with markers like `【4:0†source】` pointing at chunks; we strip those for
display and resolve the underlying file IDs against our local
`ingest-state.json` map (because Foundry only stores basenames).

#### For a customer build

Most customer agents will live behind one of these patterns:

| Surface | How threads work |
|---|---|
| **Teams bot via Copilot Studio** | Studio handles threads transparently |
| **Web app / portal** | Store `thread_id` in user session; new conversation = new thread |
| **Power Automate flow** | Stateless — new thread per invocation. Simpler. |
| **D365 form embedded copilot** | Thread per record (e.g. one per case, one per invoice) keeps context relevant |

**Multi-turn vs stateless:** for grounded knowledge agents, stateless (one thread
per question) is usually the right default. It avoids confusing context bleed
between unrelated questions and keeps token costs predictable. Switch to
multi-turn only when the user genuinely needs to follow up — e.g. an interactive
troubleshooting flow.

---

### 3.5 Evaluation — proving the agent works

This is where Foundry's pitch is strongest, and where consultants find the
most billable value.

#### In our agent

[`agents/labMemoryAgent/evals/golden.jsonl`](../agents/labMemoryAgent/evals/golden.jsonl):

```jsonl
{"query": "Why does foundryLab exist?", "expected_sources": ["foundryLab/README.md", "foundryLab/docs/vision.md"], "kind": "grounded"}
{"query": "What region is foundryLab deployed in and why?", "expected_sources": ["foundryLab/docs/learnings.md"], "kind": "grounded"}
{"query": "What is the capital of Iceland?", "expected_sources": [], "kind": "ungrounded"}
...
```

15 questions: 9 grounded one-source, 3 multi-hop, 3 deliberately out-of-scope.

[`run_eval.py`](../agents/labMemoryAgent/evals/run_eval.py) walks the dataset,
calls `ask()` for each, scores against four metrics, and writes a versioned
report to `evals/results/`:

- **`cited_expected`** — for grounded items, did the answer cite at least one
  expected source?
- **`citation_recall`** — what fraction of expected sources got cited?
- **`has_citations`** — did the agent cite anything at all?
- **`refusal_accuracy`** — for out-of-scope items, did it refuse correctly?

Across four iteration cycles:

| Run | cited_expected | citation_recall | has_citations | refusal_accuracy |
|---|---|---|---|---|
| Baseline (default temp, no path headers) | 0.67 | 0.56 | 0.83 | 1.0 |
| + Optimized prompt | 0.67 | 0.51 | 1.00 | 1.0 |
| + Path headers + 500-token chunks | 0.83 | 0.69 | 1.00 | 1.0 |
| **+ temperature=0.2 (final)** | **0.92** | **0.75** | 0.92 | 1.0 |

#### What's actually happening

The eval framework is **the difference between a demoable agent and a
sellable one**. Without it you're trusting vibes. With it you have:

- A defensible KPI: *"on this representative test set we hit 92% citation
  accuracy"*
- A regression detector: when you change the prompt, you immediately see if
  it helped or hurt
- A signal for when to stop iterating: when the score plateaus, you've hit
  the model's ceiling and need a bigger lever (different model, hierarchical
  retrieval, source doc edits)

Foundry has built-in evaluators that you can call via REST or MCP — `groundedness`,
`relevance`, `coherence`, plus a "prompt optimizer" that rewrites prompts based
on observed failures. We tried both. The conclusion was unexpected: **a
200-line Python eval runner is more valuable than the built-in tooling**
because:

1. It's portable across Foundry, Copilot Studio, and custom Azure backends —
   you write it once, reuse it everywhere
2. The MCP tools cache identity per VS Code session, breaking after tenant
   switches
3. Custom Python lets you encode domain-specific scoring rules that built-in
   evaluators don't know about

#### For a customer build

This is the section to read twice if you're trying to scope agent engagements.

**Build the golden dataset before you build the agent.** Sit with the customer's
SMEs for an afternoon and capture:

- 30–50 real questions they want the agent to answer
- For each grounded question, which document(s) the answer is in
- 5–10 deliberately out-of-scope questions to test refusal behavior

This conversation alone is more valuable than half the requirements gathering
on a typical implementation, because it forces the customer to articulate
*"what would 'good' actually look like?"*. Bill for it.

**Plan eval iteration cycles into the timeline.** Our path was:
1. baseline → 0.67
2. fix the obvious prompt issue → no change in accuracy, but stable
3. fix retrieval (path headers, chunk size) → +16 percentage points
4. fix sampling temperature → another +9 percentage points

Customer go-live should target ≥0.85 on `cited_expected` for a knowledge agent.
Below that and users will lose trust quickly.

**Continuous evaluation = production health monitoring.** Foundry has a
`continuous_eval_create` that runs your eval set periodically against
production traces and alerts on regression. It's the runtime equivalent of D365
health monitoring — set it up at go-live.

---

## Part 4 — When to use Foundry vs Copilot Studio vs custom Azure

### Decision flowchart

```text
Customer wants an agent →
   Does it live inside Microsoft 365 (Teams, Outlook, SharePoint)?
      yes → Copilot Studio (with Foundry agent as a sub-tool if reasoning needed)
      no  → Does it need RAG / evaluations / prompt iteration loop?
                yes → Foundry
                no  → Are there hard constraints Foundry can't meet?
                          yes → custom Azure Functions + AOAI
                          no  → Foundry (default — lowest TCO)
```

### Comparison table

| Dimension | **Microsoft Foundry** | **Copilot Studio** | **Custom Azure Functions + AOAI** |
|---|---|---|---|
| Primary user | Pro developer | Citizen developer / business user | Pro developer |
| Surface | SDK, Foundry portal | Low-code studio | Code (any language) |
| Pricing model | Pay-per-token + Azure | Per-message OR seat-based | Pay-per-token + Azure |
| Idle cost | **€0** | per-seat license | €0 (consumption) |
| Authentication | DefaultAzureCredential / managed identity | Microsoft 365 / Power Platform | Whatever you wire up |
| Built-in RAG | ✅ file_search, AI Search | ✅ SharePoint, Dataverse | ❌ build with AI Search |
| Built-in evaluations | ✅ batch + continuous | partial (analytics) | ❌ build yourself |
| Multi-agent orchestration | ✅ connected agents | partial | ❌ build yourself |
| Tool calling | ✅ extensible | ✅ via Power Platform connectors | ✅ raw |
| M365 / Teams native | indirect | ✅ native channel | indirect |
| Best at | Specialized agents, eval rigor, low cost | Everyday business chatbots in M365 | Total control, special compliance |
| Worst at | Quick chatbots in Teams | Heavy custom logic | Time-to-value |

### Same agent, three platforms (sketch)

Same business problem: customer wants a Q&A bot over their FDD library.

**Foundry version (what we built — adapted)**
- Bicep deploys the AOAI account + project + models
- Python ingestion script reads SharePoint via Graph, uploads to vector store
- Persistent agent + `ask()` client function exposed via REST
- Golden dataset + eval pipeline
- ~1 sprint to ship. Idle: €0. Per-query: ~€0.005.

**Copilot Studio version**
- Open Copilot Studio, create a new copilot
- Add the SharePoint library as a knowledge source (built-in connector)
- Add a topic for "answer FDD questions"
- Publish to Teams
- ~½ day to first working copilot. Cost: per-message billing or M365 Copilot
  licenses.

**Custom Azure version**
- Provision Azure AI Search index, blob storage, Functions app, Cosmos DB for
  thread state
- Write embedding pipeline, retrieval logic, RAG prompt assembly, conversation
  history management
- Write streaming response handler, citation extraction, RBAC, rate limiting
- ~4–8 sprints to reach Foundry-equivalent quality. AI Search alone runs ~€80/mo.

**Customer should rarely pick custom unless they have a specific reason.**
Foundry is the new default.

---

## Part 5 — Customer scenarios mapped to platforms (D365 F&O lens)

| Scenario | Description | Platform | Why |
|---|---|---|---|
| **Vendor invoice triage** | OCR → GL coding → exception flagging | **Foundry** | Specialized, needs eval + monitoring, called from F&O |
| **PO approval chatbot in Teams** | Approver gets a Teams card, can ask follow-ups, approves with /approve | **Copilot Studio** | M365-native, business user owns flows, connectors to F&O |
| **AP posting profile copilot** | "Why was this invoice posted to this account?" | **Copilot Studio + Foundry sub-agent** | Front-end conversation in Teams, hard reasoning delegated to a Foundry agent |
| **Production schedule assistant** | "Why did we move this work order?" from change logs in Dataverse / SCM | **Foundry** | RAG over change logs is exactly the labMemoryAgent pattern |
| **Field service dispatch** | Recommend technician based on skills, location, history | **Foundry** + connected agents | Multi-agent: route specialist, skills matcher, conflict resolver |
| **Customer service summarization** | Weekly digest of closed cases | **Copilot Studio** + Dataverse | Power Automate already does most of it |
| **Tax determination explainer** | "Why did this transaction get this tax code?" over X++ rules + setup | **Foundry** with custom function tool | Foundry agent calls an X++-driven tax engine via REST |
| **Knowledge bot for change requests** | Q&A over a project's CR register and FDDs | **Foundry** (lift our labMemoryAgent code) | Exact pattern we built |

The pattern that recurs: **front-end conversation in Copilot Studio, hard
knowledge work in a Foundry agent invoked as a tool.** This is the architecture
that scales to most enterprise rollouts.

---

## Part 6 — A first agent project to pitch a customer

When a customer says *"we want to do something with AI,"* resist the temptation
to scope-creep into a multi-agent platform. Start small and ship.

### A 2–3 sprint engagement that's defensible end-to-end

1. **Pick a knowledge corpus** the customer already maintains badly. Examples:
   - SharePoint library of customer-facing playbooks
   - Confluence space of operations runbooks
   - Folder of FDDs and change requests from a recent D365 implementation
   - Service desk knowledge base
2. **Build a Foundry agent** with file_search over that corpus. Use
   `gpt-4o-mini`, `temperature=0.2`, librarian-style instructions. **Steal
   from our labMemoryAgent code.**
3. **Build a 30-question golden dataset** with the customer's most frequent
   real questions. SMEs participate. Bill for this — it's worth it.
4. **Run the eval, iterate** prompt and ingestion until you hit ≥0.85 on
   `cited_expected`.
5. **Wire it into Teams via Copilot Studio** as a conversation surface (one
   connector call to the Foundry agent).
6. **Set up continuous evaluation** so quality regressions get flagged.

### Pricing reference

For the customer conversation:

- Idle Foundry cost: **€0**
- Per-query cost on `gpt-4o-mini`: ~€0.005
- 1 000 queries/month: ~€5
- 10 000 queries/month: ~€50
- For comparison: M365 Copilot is roughly €30/user/month — break-even calc
  is straightforward
- One-time delivery (consultant time): the fixed cost the customer cares about

A defensible POC budget is around 60–80 hours of consultant time, with hardware
costs negligible. Land that as a fixed-fee pilot, prove value with the eval
KPIs, then scope phase 2.

---

## Part 7 — Pitfalls (from our actual build)

These cost me hours; they will save you hours.

1. **Region matters more than for normal Azure work.** Northeurope had no
   consumption SKUs for AOAI and no embedding models on our subscription. We
   moved to Sweden Central. Always check
   `az cognitiveservices model list --location <region>` before committing.

2. **There are two RBAC roles you need.** "Azure AI Developer" alone is *not*
   enough to actually run an agent. You also need "Azure AI User" (data plane).
   For an agent runtime identity (managed identity), "Cognitive Services
   OpenAI User" gives inference access — but you also need "Azure AI User"
   if the runtime needs to create threads or runs.

3. **Foundry strips path prefixes from uploaded filenames.** If you upload 9
   files all called `README.md`, they all show as `README.md` in citations.
   Either embed the path inside the file content or maintain a local
   file_id → path map.

4. **Default temperature is too high for retrieval agents.** Drop it to 0.2
   if you want stable, grounded answers. **Single biggest quality lever.**

5. **Smaller chunks (500 / 120 overlap) outperform the default ~800-token
   chunks** for short markdown docs.

6. **`az account clear` is destructive, not a token refresh.** RBAC
   propagation takes minutes — just wait.

7. **Bicep `guid()` collides with manually-created role assignments.** If you
   patch RBAC manually first and add the same assignment via Bicep later,
   the deploy fails with `RoleAssignmentExists`. Always model RBAC in Bicep
   from day 1.

8. **Foundry agent runtime can be inconsistent with newly-deployed models.**
   We deployed `gpt-4o`, REST calls succeeded, but Foundry agent runs returned
   `invalid_deployment` for the same name. Workaround: declare all candidate
   models in your Phase 0 Bicep so they exist when the project is provisioned.

9. **Foundry MCP tools cache identity per VS Code session.** After tenant
   switching, MCP returns 403 until you restart VS Code. For automation,
   prefer the SDK + `DefaultAzureCredential` over MCP.

10. **The eval framework is more valuable than any individual agent.** A
    200-line Python eval runner is portable across Foundry, Copilot Studio,
    and custom code. Build it once, reuse on every customer engagement.

---

## Part 8 — Self-check (retrieval practice)

Cognitive science is clear: *retrieving* knowledge from memory builds it more
durably than re-reading. Try these without scrolling back. Answers are at the
end of this section; skip to them only after you've attempted each one.

1. What are the three Azure resource types nested inside the foundryLab
   resource group, in order from outer to inner?
2. Why does idle Foundry cost €0?
3. Name the four parts of an agent (the formula).
4. Our `temperature=0.2` change improved which metric the most, and by how
   much?
5. What did we have to do to fix Foundry's basename-collision problem on
   citations?
6. When would you pick Copilot Studio over Foundry?
7. What's the one-line pitch about cost you should give a customer
   considering a POC?
8. Why is the eval framework more reusable than any individual agent?
9. What's the recommended first customer engagement scope (in sprints)?
10. What does the `Azure AI User` role grant that `Azure AI Developer` doesn't?

<details>
<summary>Click to reveal answers</summary>

1. **Account → Project → Deployment.** Account is `Microsoft.CognitiveServices/accounts`
   of kind `AIServices`; project is a child of the account; model deployments
   are also children of the account (not the project).
2. **Consumption-based SKUs (`GlobalStandard`)** charge only per token used.
   Capacity is a per-minute throttle, not a commitment. No tokens consumed = €0.
3. **Agent = model + instructions + tools + memory.**
4. **`cited_expected` improved by ~9 percentage points** (from 0.83 to 0.92).
5. **Prepended a `# Source: <path>` header to each file's content** before
   upload, plus maintain a local `file_id → source_path` map for citation
   resolution.
6. **When the agent lives inside Microsoft 365 / Teams / Outlook**, when
   business users will own the topics, or when the customer already has
   Copilot licensing.
7. *"Idle Foundry cost is €0 — you only pay when employees use the agent.
   We can quote a capped per-query budget rather than a fixed monthly fee."*
8. **It's portable** — same Python eval runner works whether the agent is
   on Foundry, Copilot Studio, or custom Azure. The agent backend is
   replaceable; the test set survives.
9. **2–3 sprints**, scoped as: pick corpus → build Foundry agent → build
   30-question golden set → iterate to ≥0.85 → wire into Teams → enable
   continuous eval.
10. **Data-plane actions** — creating threads, runs, agents, files. AI
    Developer is mostly management plane (deploy, list); AI User is what
    you need to actually use the project.

</details>

---

## Part 9 — Where to go next

### Read

- [Microsoft Foundry overview](https://learn.microsoft.com/azure/foundry/) —
  start here, ~30 min
- [Foundry agents — file search tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/file-search) —
  the exact technique we used
- [Copilot Studio overview](https://learn.microsoft.com/microsoft-copilot-studio/) —
  required reading for any M365 customer
- [Diátaxis docs framework](https://docs.divio.com/documentation-system/) —
  the four-types model we used to structure this guide; will improve any
  other documentation you write

### Build (in order — faded examples, increasing autonomy)

1. **Replicate this lab.** Clone the foundryLab logic against a different
   corpus (your own notes, a public PDF library, whatever). Should be a
   half-day exercise once you've read this guide.
2. **Try the same scenario in Copilot Studio.** Compare developer experience
   honestly. Time-to-first-working-bot is often very different.
3. **Add a custom function tool to a Foundry agent.** Define a Python function
   like `get_d365_invoice_by_id(id) -> Invoice`, register it, watch the agent
   invoke it. **This is the bridge to integrating with D365.**
4. **Build the same with a Power Platform connector inside Copilot Studio.**
   Same scenario, low-code path.
5. **Build a connected-agents flow in Foundry.** One orchestrator + two
   specialists. This is the architecture most "AI co-worker" enterprise
   projects will ship by 2027.

### Certification

- **AI-102 (Azure AI Engineer Associate)** — fastest-moving cert, broadly
  applicable
- **PL-400 / PL-200** — relevant if leaning into the Copilot Studio side
- A Foundry-specific cert is likely within 12 months — watch the cert roadmap

---

## Appendix — useful commands

```powershell
# What models are available in a region (run this BEFORE committing to a region)
az cognitiveservices model list --location swedencentral

# What AOAI quota do you have in a region
az cognitiveservices usage list --location swedencentral

# Force a fresh AAD token (rather than `az account clear`!)
az login --tenant <your-tenant-id>

# List all agents in a Foundry project (using the SDK)
python -c "from azure.ai.agents import AgentsClient; from azure.identity import DefaultAzureCredential; c = AgentsClient(endpoint='<endpoint>', credential=DefaultAzureCredential()); [print(a.id, a.name) for a in c.list_agents()]"

# Re-run the labMemoryAgent eval (after a prompt or model change)
.\.venv\Scripts\python.exe foundryLab\agents\labMemoryAgent\evals\run_eval.py --label my-label
```

---

## TL;DR for the customer meeting

If you remember just three things:

1. **Foundry is the default for specialized, API-consumed AI agents.** Copilot
   Studio is for M365-native conversational ones. Custom code is the
   exception, not the rule.
2. **Always build an eval set.** It's the difference between an unsellable
   demo and a production-grade deliverable with KPIs the customer can audit.
3. **Idle Foundry cost is €0.** This changes the conversation about pilots
   and POCs entirely. Quote a capped per-query budget, not a fixed monthly fee.

Now go build something.
