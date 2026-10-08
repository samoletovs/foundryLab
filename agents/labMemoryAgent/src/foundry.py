"""Foundry Agent Service (v2) helpers shared by the labMemoryAgent scripts.

The classic Agents API (``azure-ai-agents``: assistants, threads, runs) is
retired on 31 March 2027. Everything here uses the new API:

* agents are versioned prompt-agent definitions created with
  ``AIProjectClient.agents.create_version``;
* they are invoked through the project's OpenAI client with
  ``responses.create(extra_body={"agent_reference": ...})``;
* vector stores and files live on that same OpenAI client.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FileSearchTool, PromptAgentDefinition
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

# Metadata key holding a hash of the definition we sent. Comparing our own hash
# avoids false "changed" verdicts from defaults the service adds on read.
FINGERPRINT_KEY = "definition_sha256"

# A cold `az` start on Windows can exceed DefaultAzureCredential's 10 s default.
CLI_PROCESS_TIMEOUT_SECONDS = 60


def make_project_client(endpoint: str) -> AIProjectClient:
    if not endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is not set; check foundryLab/.env")
    return AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(process_timeout=CLI_PROCESS_TIMEOUT_SECONDS),
    )


def build_definition(
    *, model: str, instructions: str, temperature: float, vector_store_id: str,
) -> PromptAgentDefinition:
    return PromptAgentDefinition(
        model=model,
        instructions=instructions,
        temperature=temperature,
        tools=[FileSearchTool(vector_store_ids=[vector_store_id])],
    )


def definition_fingerprint(definition: PromptAgentDefinition) -> str:
    payload = json.dumps(definition.as_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_agent_version(
    project: Any,
    agent_name: str,
    definition: PromptAgentDefinition,
    *,
    description: str = "",
) -> tuple[Any, bool]:
    """Return ``(version, created)``; only creates a version if the definition changed."""
    fingerprint = definition_fingerprint(definition)
    try:
        latest = project.agents.get(agent_name).versions.latest
    except ResourceNotFoundError:
        latest = None
    if latest is not None and (latest.metadata or {}).get(FINGERPRINT_KEY) == fingerprint:
        return latest, False
    created = project.agents.create_version(
        agent_name=agent_name,
        definition=definition,
        description=description or None,
        metadata={FINGERPRINT_KEY: fingerprint},
    )
    return created, True


def agent_reference(agent_name: str, agent_version: str | int | None) -> dict[str, str]:
    """Pinned reference: an unpinned call would silently follow any newer version."""
    if not agent_name:
        raise ValueError("agent_name is required")
    if agent_version is None or str(agent_version).strip() == "":
        raise ValueError(
            f"No version pinned for agent {agent_name!r}; run src/provision.py",
        )
    return {"name": agent_name, "version": str(agent_version), "type": "agent_reference"}


def response_error(response: Any) -> str | None:
    """Return why a Responses API result is unusable, or None if it succeeded."""
    status = getattr(response, "status", None)
    if status != "completed":
        error = getattr(response, "error", None)
        if error is not None:
            return f"response {status}: {getattr(error, 'code', '')} {getattr(error, 'message', error)}".strip()
        incomplete = getattr(response, "incomplete_details", None)
        if incomplete is not None:
            return f"response {status}: {getattr(incomplete, 'reason', incomplete)}"
        return f"response did not complete (status={status})"
    if not (getattr(response, "output_text", "") or "").strip():
        return "response completed without any output text"
    return None


def extract_answer_and_citations(response: Any) -> tuple[str, list[tuple[str, str]]]:
    """Return the answer text and ``(file_id, filename)`` file-search citations."""
    parts: list[str] = []
    citations: list[tuple[str, str]] = []
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) != "output_text":
                continue
            parts.append(content.text)
            for ann in getattr(content, "annotations", None) or []:
                if getattr(ann, "type", None) == "file_citation" and getattr(ann, "file_id", None):
                    citations.append((ann.file_id, getattr(ann, "filename", "") or ""))
    answer = "\n".join(parts).strip() or (getattr(response, "output_text", "") or "").strip()
    # Strip any inline markers like 【4:0†source】; citations are listed separately.
    answer = re.sub(r"【[^】]+】", "", answer).strip()
    return answer, citations
