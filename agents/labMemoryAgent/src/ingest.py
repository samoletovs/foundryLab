"""
labMemoryAgent ingestion pipeline.

Reads sources from `config/sources.yaml`, uploads each file to the Foundry
project, and adds them to a single named vector store. Foundry handles
chunking + embedding + indexing automatically (Basic agent setup).

Idempotent behaviour:
  - On each run we list existing vector stores by name.
  - If one already exists, we delete it and recreate. This is simpler and
    safer than diffing because the corpus is small and ingestion is fast.
  - Future enhancement: incremental updates by file path metadata.

Usage:
    python -m foundryLab.agents.labMemoryAgent.src.ingest
    # or, from the agent folder:
    python src/ingest.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    FilePurpose,
    VectorStoreExpirationPolicy,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# --- Paths ------------------------------------------------------------------

AGENT_DIR = Path(__file__).resolve().parent.parent
FOUNDRYLAB_DIR = AGENT_DIR.parent.parent
WORKSPACE_ROOT = FOUNDRYLAB_DIR.parent
CONFIG_FILE = AGENT_DIR / "config" / "sources.yaml"
ENV_FILE = FOUNDRYLAB_DIR / ".env"

VECTOR_STORE_NAME = "lab-memory"

# --- Logging ----------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
# Silence chatty Azure SDK loggers (HTTP request / identity probing)
for noisy in ("azure.core.pipeline.policies.http_logging_policy", "azure.identity"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("ingest")


# --- Models -----------------------------------------------------------------


@dataclass
class SourceFile:
    """A single resolved file to ingest, plus its metadata tags."""

    path: Path
    relative_path: str
    tags: dict[str, str]


# --- Config loading ---------------------------------------------------------


def load_sources() -> list[SourceFile]:
    """Resolve all source globs from config/sources.yaml into concrete files."""
    cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    resolved: list[SourceFile] = []
    seen: set[Path] = set()

    for entry in cfg.get("sources", []):
        name = entry["name"]
        tags = {str(k): str(v) for k, v in entry.get("tags", {}).items()}
        tags.setdefault("source_group", name)

        for raw_pattern in entry.get("paths", []):
            # Always treat patterns as relative to workspace root, forward slashes.
            pattern = raw_pattern.replace("\\", "/")
            matches = sorted(WORKSPACE_ROOT.glob(pattern))
            if not matches:
                log.warning("  no matches for %s (in group %s)", pattern, name)
                continue

            for p in matches:
                if not p.is_file():
                    continue
                if p in seen:
                    continue
                seen.add(p)
                rel = p.relative_to(WORKSPACE_ROOT).as_posix()
                file_tags = dict(tags)
                file_tags["source_path"] = rel
                resolved.append(
                    SourceFile(path=p, relative_path=rel, tags=file_tags),
                )

    return resolved


# --- Foundry helpers --------------------------------------------------------


def make_client() -> AgentsClient:
    """Build an AgentsClient pointed at the foundryLab project."""
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is not set; check foundryLab/.env")
    log.info("Foundry endpoint: %s", endpoint)
    return AgentsClient(endpoint=endpoint, credential=DefaultAzureCredential())


def find_existing_store(client: AgentsClient, name: str) -> Any | None:
    """Return existing vector store with the given name, or None."""
    for store in client.vector_stores.list():
        if store.name == name:
            return store
    return None


def delete_store_and_files(client: AgentsClient, store: Any) -> None:
    """Delete a vector store and the underlying files it contained."""
    log.info("Deleting existing vector store %s (%s)", store.name, store.id)
    file_ids: list[str] = []
    for vsf in client.vector_store_files.list(vector_store_id=store.id):
        file_ids.append(vsf.id)
    client.vector_stores.delete(vector_store_id=store.id)
    log.info("  deleted vector store; cleaning up %d file(s)", len(file_ids))
    for fid in file_ids:
        try:
            client.files.delete(file_id=fid)
        except Exception as exc:  # noqa: BLE001
            log.warning("  failed to delete file %s: %s", fid, exc)


def upload_file(client: AgentsClient, src: SourceFile) -> str:
    """Upload one file. Returns the Foundry file_id."""
    # Foundry filenames are global to the agent; prefix with source_path so they
    # remain unique even when basenames collide (e.g. several README.md).
    safe_name = src.relative_path.replace("/", "__").replace("\\", "__")
    suffix = src.path.suffix.lower()
    if suffix not in {".md", ".txt", ".json", ".yaml", ".yml"}:
        # Foundry accepts a wider range, but for v1 we only ingest plain text.
        log.warning("  skipping unsupported file type: %s", src.relative_path)
        return ""

    log.info("  upload  %s", src.relative_path)
    result = client.files.upload_and_poll(
        file_path=str(src.path),
        filename=safe_name,
        purpose=FilePurpose.AGENTS,
        polling_interval=0.5,
    )
    log.debug("    file_id=%s name=%s", result.id, getattr(result, "filename", "?"))
    return result.id


def ingest() -> None:
    load_dotenv(ENV_FILE, override=False)
    client = make_client()

    sources = load_sources()
    if not sources:
        log.error("No source files matched. Aborting.")
        sys.exit(1)

    log.info("Resolved %d source file(s) from %s", len(sources), CONFIG_FILE)
    by_group: dict[str, int] = {}
    for s in sources:
        by_group[s.tags.get("source_group", "?")] = (
            by_group.get(s.tags.get("source_group", "?"), 0) + 1
        )
    for group, count in sorted(by_group.items()):
        log.info("  %-22s %d", group, count)

    existing = find_existing_store(client, VECTOR_STORE_NAME)
    if existing:
        delete_store_and_files(client, existing)

    log.info("Uploading %d file(s) to Foundry...", len(sources))
    file_ids: list[str] = []
    file_index: list[dict[str, Any]] = []
    for src in sources:
        try:
            fid = upload_file(client, src)
            if fid:
                file_ids.append(fid)
                file_index.append(
                    {
                        "file_id": fid,
                        "source_path": src.relative_path,
                        "size_bytes": src.path.stat().st_size,
                        "tags": src.tags,
                    },
                )
        except Exception as exc:  # noqa: BLE001
            log.error("  upload failed for %s: %s", src.relative_path, exc)

    if not file_ids:
        log.error("No files uploaded successfully. Aborting.")
        sys.exit(1)

    log.info(
        "Creating vector store %r with %d file(s)...",
        VECTOR_STORE_NAME,
        len(file_ids),
    )
    store = client.vector_stores.create_and_poll(
        file_ids=file_ids,
        name=VECTOR_STORE_NAME,
        expires_after=VectorStoreExpirationPolicy(
            anchor="last_active_at",
            days=365,
        ),
        polling_interval=2.0,
    )
    log.info(
        "Vector store ready: id=%s status=%s files=%s",
        store.id,
        store.status,
        store.file_counts,
    )

    # Persist the file/chunk index so other tools can map file_id -> source path.
    index_path = AGENT_DIR / "config" / "ingest-state.json"
    index_path.write_text(
        json.dumps(
            {
                "vector_store_id": store.id,
                "vector_store_name": store.name,
                "files": file_index,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("Wrote state to %s", index_path.relative_to(WORKSPACE_ROOT))


if __name__ == "__main__":
    ingest()
