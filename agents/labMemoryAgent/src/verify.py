"""Quick verify: what's in our vector store, and which agent version is pinned?"""
import json
import os
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError
from dotenv import load_dotenv

from foundry import make_project_client

ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
AGENT_STATE_FILE = Path(__file__).resolve().parent.parent / "config" / "agent-state.json"
load_dotenv(ENV_FILE)

project = make_project_client(os.environ["FOUNDRY_PROJECT_ENDPOINT"])
c = project.get_openai_client()

print("Vector stores:")
for vs in c.vector_stores.list():
    print(f"  {vs.id}  name={vs.name!r}  status={vs.status}  files={vs.file_counts}  bytes={getattr(vs, 'usage_bytes', '?')}")

files = list(c.files.list())
total_bytes = sum(getattr(f, "bytes", 0) or 0 for f in files)
print(f"\nTotal files in project: {len(files)}")
print(f"Total size: {total_bytes/1024:.1f} KB")
print("\nSample (first 5 filenames):")
for f in files[:5]:
    fname = getattr(f, "filename", "?")
    fsize = getattr(f, "bytes", 0) or 0
    print(f"  {f.id}  {fsize:>7} B  {fname}")

if AGENT_STATE_FILE.exists():
    state = json.loads(AGENT_STATE_FILE.read_text(encoding="utf-8"))
    name = state.get("agent_name", "lab-memory")
    print(f"\nPinned agent: {name} version {state.get('agent_version', '<classic state; re-run provision.py>')}")
    try:
        latest = project.agents.get(name).versions.latest
        print(f"Latest on server: version {latest.version}  model={latest.definition.model}")
    except ResourceNotFoundError:
        print("Latest on server: <not found; run provision.py>")
