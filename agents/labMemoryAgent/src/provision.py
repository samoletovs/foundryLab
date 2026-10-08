"""
Provision (or update) the persistent labMemoryAgent in Foundry.

Uses the Foundry Agents v2 API: the agent is a named, versioned prompt-agent
definition. Idempotent: a new version is created only when the definition
(model, instructions, temperature, vector store) differs from the latest one;
otherwise the latest version is reused. Writes the resolved name + version to
config/agent-state.json so client.py can pin it.

Usage:
    python -m foundryLab.agents.labMemoryAgent.src.provision
    # or:
    python src/provision.py
"""
from __future__ import annotations

import logging
import sys

from config import (
    AGENT_NAME,
    DEPLOYMENT,
    INSTRUCTIONS,
    PROJECT_ENDPOINT,
    TEMPERATURE,
    load_ingest_state,
    save_agent_state,
)
from foundry import build_definition, ensure_agent_version, make_project_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("azure.core.pipeline.policies.http_logging_policy", "azure.identity", "httpx"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("provision")

DESCRIPTION = "NauroLabs librarian: grounded answers over the lab-memory vector store."


def provision() -> int:
    state = load_ingest_state()
    vector_store_id = state["vector_store_id"]
    log.info("Vector store: %s (%s)", state["vector_store_name"], vector_store_id)
    log.info("Model deployment %s  (temperature=%.2f)", DEPLOYMENT, TEMPERATURE)

    project = make_project_client(PROJECT_ENDPOINT)
    store = project.get_openai_client().vector_stores.retrieve(vector_store_id)
    if store.status != "completed":
        log.error("Vector store %s is %s, not completed; re-run src/ingest.py", store.id, store.status)
        return 1
    log.info("Vector store visible: status=%s files=%s", store.status, store.file_counts.completed)

    definition = build_definition(
        model=DEPLOYMENT,
        instructions=INSTRUCTIONS,
        temperature=TEMPERATURE,
        vector_store_id=vector_store_id,
    )
    version, created = ensure_agent_version(
        project, AGENT_NAME, definition, description=DESCRIPTION,
    )
    verb = "Created new" if created else "Unchanged; reusing"
    log.info("%s agent version: name=%s version=%s id=%s", verb, version.name, version.version, version.id)

    save_agent_state(
        {
            "api": "foundry-agents-v2",
            "agent_name": version.name,
            "agent_version": str(version.version),
            "agent_version_id": version.id,
            "model": DEPLOYMENT,
            "temperature": TEMPERATURE,
            "vector_store_id": vector_store_id,
        },
    )
    log.info("Saved agent state to config/agent-state.json")
    return 0


if __name__ == "__main__":
    sys.exit(provision())
