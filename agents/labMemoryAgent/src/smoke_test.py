"""
Phase 1 acceptance test: create a temporary librarian agent backed by the
lab-memory vector store, ask 3 grounded questions, and 1 unanswerable one.

This validates that:
  - the vector store is queryable
  - the file_search tool returns sensible chunks
  - the model produces answers grounded in our docs

The agent is deleted at the end — production agent is provisioned in Phase 2.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    FileSearchTool,
    ListSortOrder,
    MessageRole,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
STATE_FILE = Path(__file__).resolve().parent.parent / "config" / "ingest-state.json"
load_dotenv(ENV_FILE)

state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
vector_store_id = state["vector_store_id"]
deployment = os.environ["FOUNDRY_DEFAULT_DEPLOYMENT"]
endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

QUESTIONS_GROUNDED = [
    "Why does foundryLab exist?",
    "What is rosette and what tech stack does it use?",
    "What does WORKSPACE.md say about creating a new project?",
]
QUESTION_UNGROUNDED = "What is the capital of Mongolia?"

INSTRUCTIONS = """You are the NauroLabs librarian. Answer questions about the
NauroLabs lab using ONLY information retrieved from the attached vector store.

Rules:
1. If the answer is in the documents, give it concisely and cite the source filename(s).
2. If the answer is NOT in the documents, say exactly: "I don't know — that's not in the lab documents."
3. Never invent facts. Never use general world knowledge."""


def main() -> int:
    client = AgentsClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )

    print(f"Using vector store {vector_store_id}\n")

    file_search = FileSearchTool(vector_store_ids=[vector_store_id])

    agent = client.create_agent(
        model=deployment,
        name="lab-memory-test",
        instructions=INSTRUCTIONS,
        tools=file_search.definitions,
        tool_resources=file_search.resources,
    )
    print(f"Created test agent {agent.id}\n")

    failures = 0
    try:
        for i, question in enumerate(QUESTIONS_GROUNDED + [QUESTION_UNGROUNDED]):
            if i > 0:
                # Default deployment is 50K TPM; file_search responses are
                # token-heavy (~5-15K each). Sleep between questions to stay
                # well under the limit during this smoke test.
                time.sleep(45)
            thread = client.threads.create()
            client.messages.create(
                thread_id=thread.id, role=MessageRole.USER, content=question
            )
            run = client.runs.create_and_process(
                thread_id=thread.id, agent_id=agent.id
            )
            print(f"Q: {question}")
            print(f"   run.status = {run.status}")
            if run.status != "completed":
                print(f"   run.last_error = {run.last_error}")
                failures += 1
                client.threads.delete(thread.id)
                continue

            msgs = list(
                client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
            )
            answer_msg = next(
                m for m in reversed(msgs) if m.role == MessageRole.AGENT
            )
            answer_text = "\n".join(
                t.text.value for t in answer_msg.text_messages
            ).strip()
            print(f"A: {answer_text[:500]}")
            print()
            client.threads.delete(thread.id)

            if question == QUESTION_UNGROUNDED:
                if "I don't know" not in answer_text:
                    print("  ⚠ FAIL: should have refused")
                    failures += 1
                else:
                    print("  ✓ refused correctly")
                    print()
    finally:
        client.delete_agent(agent.id)
        print(f"Deleted test agent {agent.id}")

    return failures


if __name__ == "__main__":
    sys.exit(main())
