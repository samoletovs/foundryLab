"""Offline checks for the synthetic migration gate itself."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from openai.types.chat import ChatCompletion

path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_model_refresh.py"
spec = importlib.util.spec_from_file_location("model_refresh_eval", path)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def completion(content: str, finish: str = "stop") -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "synthetic", "created": 0, "object": "chat.completion",
        "model": "test", "choices": [{
            "index": 0, "finish_reason": finish,
            "message": {"role": "assistant", "content": content},
        }],
    })


class ContractGraderTests(unittest.TestCase):
    def test_accepts_correct_meaning(self) -> None:
        mod.check_json(completion('{"change_pct":25}'), {"change_pct": 25})

    def test_rejects_valid_json_with_wrong_answer(self) -> None:
        with self.assertRaises(ValueError):
            mod.check_json(completion('{"change_pct":20}'), {"change_pct": 25})

    def test_rejects_unexpected_fields(self) -> None:
        with self.assertRaises(ValueError):
            mod.check_json(completion('{"price_eur":null,"invented":9}'), {"price_eur": None})

    def test_rejects_number_in_place_of_boolean(self) -> None:
        with self.assertRaises(ValueError):
            mod.check_json(completion('{"retry_allowed":0}'), {"retry_allowed": False})

    def test_truncated_correct_json_is_still_failure(self) -> None:
        with self.assertRaises(ValueError):
            mod.check_json(completion('{"result":42}', "length"), {"result": 42})

    def test_budget_rejects_call_before_contacting_provider(self) -> None:
        from unittest.mock import Mock

        client = Mock()
        evaluation = mod.Evaluation(client, 0.000001)
        with self.assertRaisesRegex(ValueError, "ceiling"):
            evaluation.call("gpt-6-sol", [{"role": "user", "content": "Return JSON"}])
        client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
