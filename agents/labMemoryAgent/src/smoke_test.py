"""
Phase 1 acceptance test: create a temporary librarian agent backed by the
lab-memory vector store, ask 3 grounded questions, and 1 unanswerable one.

This validates that:
  - the vector store is queryable
  - the file_search tool returns sensible chunks
  - the model produces answers grounded in our docs

The temporary agent (all its versions) is deleted at the end — the production
agent is provisioned by provision.py.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from client import ask_with
from foundry import build_definition, make_project_client

ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
STATE_FILE = Path(__file__).resolve().parent.parent / "config" / "ingest-state.json"
load_dotenv(ENV_FILE)

state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
vector_store_id = state["vector_store_id"]
file_id_to_path = {f["file_id"]: f["source_path"] for f in state["files"]}
deployment = os.environ["FOUNDRY_DEFAULT_DEPLOYMENT"]
endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

TEST_AGENT_NAME = "lab-memory-test"

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
    project = make_project_client(endpoint)
    openai_client = project.get_openai_client()

    print(f"Using vector store {vector_store_id}\n")

    agent = project.agents.create_version(
        agent_name=TEST_AGENT_NAME,
        definition=build_definition(
            model=deployment,
            instructions=INSTRUCTIONS,
            temperature=0.2,
            vector_store_id=vector_store_id,
        ),
    )
    print(f"Created test agent {agent.name} version {agent.version}\n")

    failures = 0
    try:
        for i, question in enumerate(QUESTIONS_GROUNDED + [QUESTION_UNGROUNDED]):
            if i > 0:
                # Default deployment is 50K TPM; file_search responses are
                # token-heavy (~5-15K each). Sleep between questions to stay
                # well under the limit during this smoke test.
                time.sleep(45)
            result = ask_with(
                openai_client,
                agent_name=agent.name,
                agent_version=agent.version,
                file_id_to_path=file_id_to_path,
                question=question,
            )
            print(f"Q: {question}")
            print(f"   response.status = {result.raw_status}  id = {result.response_id}")
            if result.error:
                print(f"   response.error = {result.error}")
                failures += 1
                continue

            print(f"A: {result.answer[:500]}")
            for source in result.citations:
                print(f"   source: {source}")
            print()

            if question == QUESTION_UNGROUNDED:
                if "I don't know" not in result.answer:
                    print("  ⚠ FAIL: should have refused")
                    failures += 1
                else:
                    print("  ✓ refused correctly")
                    print()
    finally:
        project.agents.delete(TEST_AGENT_NAME)
        print(f"Deleted test agent {TEST_AGENT_NAME}")

    return failures


if __name__ == "__main__":
    sys.exit(main())
