"""Diagnose the agent's current state (looked up by name, not by a stored id)."""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR / "src"))

from config import AGENT_NAME  # noqa: E402
from foundry import make_project_client  # noqa: E402

load_dotenv(AGENT_DIR.parent.parent / ".env")
project = make_project_client(os.environ["FOUNDRY_PROJECT_ENDPOINT"])

agent = project.agents.get(AGENT_NAME).versions.latest
definition = agent.definition
print(f"name={agent.name}")
print(f"version={agent.version}  (latest)")
print(f"model={definition.model}")
print(f"temperature={getattr(definition, 'temperature', '?')}")
print(f"tools={[t.type for t in (definition.tools or [])]}")
print(f"vector_store_ids={[getattr(t, 'vector_store_ids', None) for t in (definition.tools or [])]}")

state_file = AGENT_DIR / "config" / "agent-state.json"
if state_file.exists():
    pinned = json.loads(state_file.read_text(encoding="utf-8")).get("agent_version")
    print(f"pinned_by_client={pinned}")
