"""Shared constants for labMemoryAgent.

Single place to change the agent name, store name, model, instructions, etc.
Both provision.py and client.py read from here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# --- Paths ---
AGENT_DIR = Path(__file__).resolve().parent.parent
FOUNDRYLAB_DIR = AGENT_DIR.parent.parent
WORKSPACE_ROOT = FOUNDRYLAB_DIR.parent
ENV_FILE = FOUNDRYLAB_DIR / ".env"
INGEST_STATE_FILE = AGENT_DIR / "config" / "ingest-state.json"
AGENT_STATE_FILE = AGENT_DIR / "config" / "agent-state.json"

load_dotenv(ENV_FILE, override=False)

# --- Names / IDs ---
AGENT_NAME = "lab-memory"
VECTOR_STORE_NAME = "lab-memory"

# --- Foundry config (from .env) ---
PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
# Stay on gpt-4o-mini for now. We tried switching to gpt-4o (deployed, has
# assistants=true, callable via REST) but the Foundry agent runtime returns
# invalid_deployment. Documented in docs/learnings.md as an open issue.
DEPLOYMENT = os.environ.get("LAB_MEMORY_DEPLOYMENT", "gpt-4o-mini")

# Low temperature for grounded-fact retrieval; default is ~1.0 which gives
# stochastic answers across reruns.
TEMPERATURE = 0.2

# --- Persona ---
INSTRUCTIONS = """You are the NauroLabs librarian. Your primary role is to answer questions about the NauroLabs lab using ONLY information retrieved from the attached vector store.

Rules:
1. Always call the file_search tool before answering any grounded question.
2. Prefer the MOST SPECIFIC matching document over a generic one when citing sources. For example, prioritize foundryLab/docs/learnings.md over foundryLab/README.md for specific queries.
3. Cite at least 1–2 source files for every grounded answer.
4. If the answer is NOT in the documents, respond exactly with: "I don't know — that's not in the lab documents."
5. Recognize and categorize report types:
   - .github/reports/plan/*.md = strategic recommendations from nauro-plan
   - .github/reports/ops/*.md = operations/cost/health from nauro-ops
   - .github/reports/run/*.md = combined cycle output from nauro-run
6. Prefer current information over older reports. When reports conflict, mention the date and prefer the most recent.
7. For strategic questions like "what should I work on" or "what's next," prioritize nauro-plan reports.

Your responses should be direct and concise, grounded in the retrieved documents."""


def load_ingest_state() -> dict:
    """Read the latest ingest-state.json to find the current vector store ID."""
    if not INGEST_STATE_FILE.exists():
        raise RuntimeError(
            f"{INGEST_STATE_FILE} missing. Run src/ingest.py first.",
        )
    return json.loads(INGEST_STATE_FILE.read_text(encoding="utf-8"))


def load_agent_state() -> dict | None:
    """Read the persisted agent ID, if provision.py has been run."""
    if not AGENT_STATE_FILE.exists():
        return None
    return json.loads(AGENT_STATE_FILE.read_text(encoding="utf-8"))


def save_agent_state(data: dict) -> None:
    AGENT_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
