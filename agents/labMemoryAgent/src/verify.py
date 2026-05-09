"""Quick verify: what's in our vector store?"""
import os
from pathlib import Path

from azure.ai.agents import AgentsClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(ENV_FILE)

c = AgentsClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

print("Vector stores:")
for vs in c.vector_stores.list():
    print(f"  {vs.id}  name={vs.name!r}  status={vs.status}  files={vs.file_counts}  bytes={getattr(vs, 'usage_bytes', '?')}")

files = list(c.files.list())
total_bytes = sum(getattr(f, "size", 0) or getattr(f, "bytes", 0) for f in files)
print(f"\nTotal files in project: {len(files)}")
print(f"Total size: {total_bytes/1024:.1f} KB")
print(f"\nSample (first 5 filenames):")
for f in files[:5]:
    fname = getattr(f, "filename", "?")
    fsize = getattr(f, "size", 0) or getattr(f, "bytes", 0)
    print(f"  {f.id}  {fsize:>7} B  {fname}")
