"""
Provision (or update) the persistent labMemoryAgent in Foundry.

Idempotent: looks up an existing agent by name and updates it; creates a new one
if not found. Writes the resolved agent_id to config/agent-state.json so other
tools can locate it.

Usage:
    python -m foundryLab.agents.labMemoryAgent.src.provision
    # or:
    python src/provision.py
"""
from __future__ import annotations

import logging

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FileSearchTool
from azure.identity import DefaultAzureCredential

from config import (
    AGENT_NAME,
    DEPLOYMENT,
    INSTRUCTIONS,
    PROJECT_ENDPOINT,
    TEMPERATURE,
    load_ingest_state,
    save_agent_state,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("azure.core.pipeline.policies.http_logging_policy", "azure.identity"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("provision")


def find_existing_agent(client: AgentsClient, name: str):
    for agent in client.list_agents():
        if agent.name == name:
            return agent
    return None


def provision() -> None:
    state = load_ingest_state()
    vector_store_id = state["vector_store_id"]
    log.info("Vector store: %s (%s)", state["vector_store_name"], vector_store_id)
    log.info("Project endp %s  (temperature=%.2f)", DEPLOYMENT, TEMPERATURE)

    client = AgentsClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    file_search = FileSearchTool(vector_store_ids=[vector_store_id])

    existing = find_existing_agent(client, AGENT_NAME)
    if existing:
        log.info("Updating existing agent %s (%s)...", AGENT_NAME, existing.id)
        agent = client.update_agent(
            agent_id=existing.id,
            model=DEPLOYMENT,
            instructions=INSTRUCTIONS,
            tools=file_search.definitions,
            tool_resources=file_search.resources,
            temperature=TEMPERATURE,
        )
    else:
        log.info("Creating agent %r...", AGENT_NAME)
        agent = client.create_agent(
            model=DEPLOYMENT,
            name=AGENT_NAME,
            instructions=INSTRUCTIONS,
            tools=file_search.definitions,
            tool_resources=file_search.resources,
            temperature=TEMPERATURE,
        )

    log.info("Agent ready: id=%s name=%s", agent.id, agent.name)
    save_agent_state(
        {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "model": DEPLOYMENT,
            "temperature": TEMPERATURE,
            "vector_store_id": vector_store_id,
        },
    )
    log.info("Saved agent state to config/agent-state.json")


if __name__ == "__main__":
    provision()
