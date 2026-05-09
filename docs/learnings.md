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

### 2026-05-09 — Bicep gotchas during first deploy
**Observation:** Two issues hit during first deploy:
1. `Microsoft.Insights/diagnosticSettings@2021-05-01` does not exist.
   Supported is `2021-05-01-preview` (despite the version string suggesting
   GA). Fixed by switching to `-preview`.
2. `az deployment group create --output json` mixes Bicep CLI warnings
   (sent to stderr) into the captured stdout when using PowerShell
   pipelines, breaking `ConvertFrom-Json`. Fixed by using `--output none`
   for the deploy and a separate `az deployment group show ... -o json`
   call to fetch outputs cleanly.
**Implication:** Future Bicep templates in this workspace should use
`@2021-05-01-preview` for diagnostic settings, and any deploy script
that needs to parse outputs should fetch them in a separate call.
**Action:** Both fixes committed. Worth propagating pattern #2 to other
projects' deploy scripts (agentMode, era).


