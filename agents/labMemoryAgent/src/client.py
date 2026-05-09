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
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ListSortOrder, MessageRole
from azure.identity import DefaultAzureCredential

from config import PROJECT_ENDPOINT, load_agent_state, load_ingest_state


@dataclass
class AskResult:
    answer: str
    citations: list[str] = field(default_factory=list)
    raw_status: str = ""
    error: str | None = None


_client: AgentsClient | None = None
_agent_id: str | None = None
_file_id_to_path: dict[str, str] | None = None


def _ensure_initialized() -> tuple[AgentsClient, str, dict[str, str]]:
    """Lazy initialize client, agent_id, and file-id-to-path map."""
    global _client, _agent_id, _file_id_to_path
    if _client is not None and _agent_id is not None and _file_id_to_path is not None:
        return _client, _agent_id, _file_id_to_path

    state = load_agent_state()
    if not state:
        raise RuntimeError(
            "No agent state found. Run src/provision.py to create the agent.",
        )

    ingest = load_ingest_state()
    # Foundry only stores the basename of an uploaded file, so multiple files
    # with the same basename (e.g. several README.md) would be indistinguishable
    # in citations. We keep a local mapping file_id -> original source path
    # in ingest-state.json and use it to resolve citations correctly.
    _file_id_to_path = {f["file_id"]: f["source_path"] for f in ingest["files"]}

    _client = AgentsClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )
    _agent_id = state["agent_id"]
    return _client, _agent_id, _file_id_to_path


def _extract_answer_and_citations(message) -> tuple[str, list[str]]:
    """Pull text + file citation annotations out of an agent message."""
    parts: list[str] = []
    file_ids: list[str] = []
    for block in message.text_messages:
        text = block.text.value
        annotations = getattr(block.text, "annotations", None) or []
        for ann in annotations:
            fc = getattr(ann, "file_citation", None)
            if fc is None:
                continue
            file_id = getattr(fc, "file_id", None)
            if file_id:
                file_ids.append(file_id)
        parts.append(text)
    answer = "\n".join(parts).strip()
    # Strip the inline cite markers like 【4:0†source】 since we surface
    # citations as a separate list.
    answer = re.sub(r"【[^】]+】", "", answer).strip()
    return answer, file_ids


def ask(question: str, *, conversation_id: str | None = None) -> AskResult:
    """Ask the labMemoryAgent a question. Returns AskResult."""
    client, agent_id, file_id_to_path = _ensure_initialized()

    thread = client.threads.create() if conversation_id is None else None
    thread_id = conversation_id or thread.id

    try:
        client.messages.create(
            thread_id=thread_id,
            role=MessageRole.USER,
            content=question,
        )
        run = client.runs.create_and_process(
            thread_id=thread_id,
            agent_id=agent_id,
        )
        if str(run.status) != "RunStatus.COMPLETED" and run.status != "completed":
            err = getattr(run, "last_error", None)
            return AskResult(
                answer="",
                raw_status=str(run.status),
                error=str(err) if err else "run did not complete",
            )

        msgs = list(
            client.messages.list(
                thread_id=thread_id,
                order=ListSortOrder.ASCENDING,
            ),
        )
        agent_msg = next(m for m in reversed(msgs) if m.role == MessageRole.AGENT)
        answer, file_ids = _extract_answer_and_citations(agent_msg)

        # Resolve file_ids to ORIGINAL source paths (forward-slash) using the
        # local ingest-state map. Foundry only stores file basenames so this
        # local mapping is the single source of truth for unique citations.
        citations: list[str] = []
        seen: set[str] = set()
        for fid in file_ids:
            if fid in seen:
                continue
            seen.add(fid)
            if fid in file_id_to_path:
                citations.append(file_id_to_path[fid])
                continue
            # Fallback: query Foundry for the basename if not in our map
            try:
                f = client.files.get(file_id=fid)
                citations.append(getattr(f, "filename", fid))
            except Exception:  # noqa: BLE001
                citations.append(fid)

        return AskResult(
            answer=answer,
            citations=citations,
            raw_status=str(run.status),
        )
    finally:
        if conversation_id is None:
            client.threads.delete(thread_id)
