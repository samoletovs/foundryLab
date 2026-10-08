"""Offline checks for the labMemoryAgent migration to Foundry Agents v2.

Fake clients only; nothing here calls Azure.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from openai.types.responses import Response

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "agents" / "labMemoryAgent"
sys.path.insert(0, str(AGENT_DIR / "src"))

import client  # noqa: E402
import foundry  # noqa: E402

FILE_MAP = {"assistant-A": "foundryLab/docs/learnings.md"}


def make_response(status: str = "completed", text: str = "Sweden Central.", **extra: Any) -> Response:
    output: list[dict[str, Any]] = [
        {"type": "file_search_call", "id": "fs_1", "status": "completed", "queries": ["region"]},
    ]
    if text:
        output.append({
            "type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{
                "type": "output_text", "text": text + "【4:0†source】",
                "annotations": [
                    {"type": "file_citation", "file_id": "assistant-A", "filename": "learnings.md", "index": 3},
                    {"type": "file_citation", "file_id": "assistant-A", "filename": "learnings.md", "index": 9},
                    {"type": "file_citation", "file_id": "assistant-Z", "filename": "orphan.md", "index": 12},
                ],
            }],
        })
    return Response.model_validate({
        "id": "resp_1", "created_at": 0, "model": "gpt-4o-mini", "object": "response",
        "status": status, "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
        "output": output, **extra,
    })


class StrictFakeOpenAI:
    """Mimics the Responses endpoint, refusing calls that are not pinned to an agent version."""

    def __init__(self, response: Response) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responses = SimpleNamespace(create=self._create)
        self._response = response

    def _create(self, **kwargs: Any) -> Response:
        ref = (kwargs.get("extra_body") or {}).get("agent_reference")
        if not ref or ref.get("type") != "agent_reference" or not ref.get("name") or not ref.get("version"):
            raise AssertionError(f"responses.create called without a pinned agent_reference: {kwargs}")
        if "model" in kwargs or "instructions" in kwargs:
            raise AssertionError("agent calls must not override model/instructions")
        self.calls.append(kwargs)
        return self._response


def ask(fake: StrictFakeOpenAI, **overrides: Any) -> client.AskResult:
    args: dict[str, Any] = {
        "agent_name": "lab-memory", "agent_version": "3",
        "file_id_to_path": FILE_MAP, "question": "Which region?",
    }
    args.update(overrides)
    return client.ask_with(fake, **args)


class AgentReferenceTests(unittest.TestCase):
    def test_sends_name_and_pinned_version(self) -> None:
        fake = StrictFakeOpenAI(make_response())
        ask(fake)
        self.assertEqual(
            fake.calls[0]["extra_body"]["agent_reference"],
            {"name": "lab-memory", "version": "3", "type": "agent_reference"},
        )

    def test_refuses_to_call_without_a_version(self) -> None:
        fake = StrictFakeOpenAI(make_response())
        for missing in (None, ""):
            with self.assertRaises(ValueError):
                ask(fake, agent_version=missing)
        self.assertEqual(fake.calls, [])

    def test_one_shot_is_not_stored_but_conversation_is_reused(self) -> None:
        fake = StrictFakeOpenAI(make_response())
        ask(fake)
        ask(fake, conversation_id="conv_1")
        self.assertIs(fake.calls[0]["store"], False)
        self.assertNotIn("conversation", fake.calls[0])
        self.assertEqual(fake.calls[1]["conversation"], "conv_1")


class FailureIsNotSuccessTests(unittest.TestCase):
    def assert_failure(self, result: client.AskResult) -> None:
        self.assertTrue(result.error, "a failed response must carry an error")
        self.assertEqual(result.answer, "")
        self.assertEqual(result.citations, [])

    def test_failed_response_is_an_error(self) -> None:
        response = make_response("failed", error={"code": "server_error", "message": "boom"})
        result = ask(StrictFakeOpenAI(response))
        self.assert_failure(result)
        self.assertIn("boom", result.error or "")
        self.assertEqual(result.raw_status, "failed")

    def test_incomplete_response_is_an_error_even_with_partial_text(self) -> None:
        response = make_response("incomplete", incomplete_details={"reason": "max_output_tokens"})
        result = ask(StrictFakeOpenAI(response))
        self.assert_failure(result)
        self.assertIn("max_output_tokens", result.error or "")

    def test_completed_without_text_is_an_error(self) -> None:
        self.assert_failure(ask(StrictFakeOpenAI(make_response(text=""))))

    def test_cli_exits_non_zero_on_failure(self) -> None:
        import ask as ask_cli

        failed = client.AskResult(answer="", raw_status="failed", error="response failed")
        original_ask, original_argv = ask_cli.ask, sys.argv
        ask_cli.ask, sys.argv = (lambda q: failed), ["ask.py", "q"]
        try:
            self.assertEqual(ask_cli.main(), 1)
        finally:
            ask_cli.ask, sys.argv = original_ask, original_argv


class CitationTests(unittest.TestCase):
    def test_completed_answer_surfaces_deduplicated_source_paths(self) -> None:
        result = ask(StrictFakeOpenAI(make_response()))
        self.assertIsNone(result.error)
        self.assertEqual(result.answer, "Sweden Central.")
        self.assertEqual(result.citations, ["foundryLab/docs/learnings.md", "orphan.md"])
        self.assertEqual((result.response_id, result.agent_version), ("resp_1", "3"))


class FakeAgents:
    def __init__(self, latest: Any | None) -> None:
        self.latest = latest
        self.created: list[dict[str, Any]] = []

    def get(self, agent_name: str) -> Any:
        if self.latest is None:
            raise ResourceNotFoundError("not found")
        return SimpleNamespace(versions=SimpleNamespace(latest=self.latest))

    def create_version(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        return SimpleNamespace(name=kwargs["agent_name"], version="2", metadata=kwargs["metadata"])


class IdempotentVersioningTests(unittest.TestCase):
    def definition(self, temperature: float = 0.2) -> Any:
        return foundry.build_definition(
            model="gpt-4o-mini", instructions="x", temperature=temperature, vector_store_id="vs_1",
        )

    def test_creates_first_version(self) -> None:
        agents = FakeAgents(latest=None)
        _, created = foundry.ensure_agent_version(SimpleNamespace(agents=agents), "lab-memory", self.definition())
        self.assertTrue(created)
        tool = agents.created[0]["definition"].tools[0]
        self.assertEqual((tool.type, tool.vector_store_ids), ("file_search", ["vs_1"]))

    def test_reuses_unchanged_definition(self) -> None:
        fingerprint = foundry.definition_fingerprint(self.definition())
        latest = SimpleNamespace(version="1", metadata={foundry.FINGERPRINT_KEY: fingerprint})
        agents = FakeAgents(latest=latest)
        version, created = foundry.ensure_agent_version(SimpleNamespace(agents=agents), "lab-memory", self.definition())
        self.assertFalse(created)
        self.assertIs(version, latest)
        self.assertEqual(agents.created, [])

    def test_changed_definition_creates_new_version(self) -> None:
        fingerprint = foundry.definition_fingerprint(self.definition())
        agents = FakeAgents(latest=SimpleNamespace(version="1", metadata={foundry.FINGERPRINT_KEY: fingerprint}))
        _, created = foundry.ensure_agent_version(
            SimpleNamespace(agents=agents), "lab-memory", self.definition(temperature=0.5),
        )
        self.assertTrue(created)


class ClassicApiRemovedTests(unittest.TestCase):
    def test_requirements_drop_azure_ai_agents(self) -> None:
        text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
        packages = [line.split("#")[0].strip() for line in text.splitlines()]
        self.assertFalse([p for p in packages if p.lower().startswith("azure-ai-agents")])
        self.assertIn("azure-ai-projects>=2.1.0,<3", packages)

    def test_no_python_file_imports_the_classic_sdk(self) -> None:
        pattern = re.compile(r"^\s*(from|import)\s+azure\.ai\.agents\b", re.MULTILINE)
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path in REPO_ROOT.rglob("*.py")
            if ".venv" not in path.parts and pattern.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
