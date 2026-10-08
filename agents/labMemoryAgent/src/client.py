"""
Reusable client for labMemoryAgent.

Other agents/tools can import `ask()` and get a grounded answer from the
NauroLabs librarian.

Example:
    from client import ask
    result = ask("Why did we drop X feature in rosette?")
    print(result.answer)
    for c in result.citations:
        print(" -", c)

Multi-turn (the agent remembers earlier turns of the same conversation):
    from client import ask, new_conversation
    conv = new_conversation()
    ask("What is rosette?", conversation_id=conv)
    ask("And what stack does it use?", conversation_id=conv)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import openai

from config import PROJECT_ENDPOINT, load_agent_state, load_ingest_state
from foundry import (
    agent_reference,
    extract_answer_and_citations,
    make_project_client,
    response_error,
)


@dataclass
class AskResult:
    answer: str
    citations: list[str] = field(default_factory=list)
    raw_status: str = ""
    error: str | None = None
    response_id: str | None = None
    agent_version: str | None = None


@dataclass
class _Session:
    project: Any
    openai_client: Any
    agent_name: str
    agent_version: str
    file_id_to_path: dict[str, str]


_session: _Session | None = None


def _ensure_initialized() -> _Session:
    """Lazy initialize the clients, pinned agent version and file-id map."""
    global _session
    if _session is not None:
        return _session

    state = load_agent_state()
    if not state:
        raise RuntimeError(
            "No agent state found. Run src/provision.py to create the agent.",
        )
    if not state.get("agent_version"):
        raise RuntimeError(
            "config/agent-state.json was written by the classic Agents API "
            "(no agent_version). Re-run src/provision.py to create the "
            "Foundry Agents v2 version.",
        )

    ingest = load_ingest_state()
    # Foundry only stores the basename of an uploaded file, so multiple files
    # with the same basename (e.g. several README.md) would be indistinguishable
    # in citations. We keep a local mapping file_id -> original source path
    # in ingest-state.json and use it to resolve citations correctly.
    file_id_to_path = {f["file_id"]: f["source_path"] for f in ingest["files"]}

    project = make_project_client(PROJECT_ENDPOINT)
    _session = _Session(
        project=project,
        openai_client=project.get_openai_client(),
        agent_name=state["agent_name"],
        agent_version=str(state["agent_version"]),
        file_id_to_path=file_id_to_path,
    )
    return _session


def ask_with(
    openai_client: Any,
    *,
    agent_name: str,
    agent_version: str,
    file_id_to_path: dict[str, str],
    question: str,
    conversation_id: str | None = None,
) -> AskResult:
    """Ask a specific pinned agent version through an OpenAI-compatible client."""
    reference = agent_reference(agent_name, agent_version)
    # One-shot questions are not stored (like the old delete-thread-after-use);
    # a conversation id makes the service keep and replay prior turns.
    turn = {"conversation": conversation_id} if conversation_id else {"store": False}
    try:
        response = openai_client.responses.create(
            input=question,
            extra_body={"agent_reference": reference},
            **turn,
        )
    except openai.APIError as exc:
        return AskResult(
            answer="",
            raw_status="error",
            error=f"{type(exc).__name__}: {exc}",
            agent_version=reference["version"],
        )

    status = str(getattr(response, "status", "") or "")
    response_id = getattr(response, "id", None)
    error = response_error(response)
    if error:
        return AskResult(
            answer="",
            raw_status=status,
            error=error,
            response_id=response_id,
            agent_version=reference["version"],
        )

    answer, file_citations = extract_answer_and_citations(response)

    # Resolve file_ids to ORIGINAL source paths (forward-slash) using the
    # local ingest-state map. Foundry only stores file basenames so this
    # local mapping is the single source of truth for unique citations.
    citations: list[str] = []
    seen: set[str] = set()
    for file_id, filename in file_citations:
        if file_id in seen:
            continue
        seen.add(file_id)
        citations.append(file_id_to_path.get(file_id) or filename or file_id)

    return AskResult(
        answer=answer,
        citations=citations,
        raw_status=status,
        response_id=response_id,
        agent_version=reference["version"],
    )


def new_conversation() -> str:
    """Create a server-side conversation for multi-turn use with `ask()`."""
    session = _ensure_initialized()
    return session.openai_client.conversations.create().id


def ask(question: str, *, conversation_id: str | None = None) -> AskResult:
    """Ask the labMemoryAgent a question. Returns AskResult."""
    session = _ensure_initialized()
    return ask_with(
        session.openai_client,
        agent_name=session.agent_name,
        agent_version=session.agent_version,
        file_id_to_path=session.file_id_to_path,
        question=question,
        conversation_id=conversation_id,
    )
