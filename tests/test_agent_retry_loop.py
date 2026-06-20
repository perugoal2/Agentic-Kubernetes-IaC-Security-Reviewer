import sys
import types
import unittest
from unittest.mock import patch

anthropic_stub = types.ModuleType("anthropic")
dotenv_stub = types.ModuleType("dotenv")


class _FakeAnthropicClient:
    def __init__(self, api_key=None):
        self.messages = types.SimpleNamespace(create=lambda **kwargs: None)


anthropic_stub.Anthropic = _FakeAnthropicClient
sys.modules.setdefault("anthropic", anthropic_stub)
dotenv_stub.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_stub)

import agent


class FakeBlock:
    def __init__(self, block_type, **kwargs):
        self.type = block_type
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class RetryLoopTests(unittest.TestCase):
    def _message_texts(self, create_mock):
        texts = []
        for call in create_mock.call_args_list:
            for message in call.kwargs["messages"]:
                content = message["content"]
                if not isinstance(content, list):
                    continue

                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item["text"])
        return texts

    def test_stops_after_validation_success(self):
        responses = [
            FakeResponse(
                "tool_use",
                [
                    FakeBlock("tool_use", id="patch-1", name="propose_patch", input={"path": "fixtures/bad.yaml", "fixed_content": "fixed"}),
                    FakeBlock("tool_use", id="validate-1", name="validate_patch", input={"original_path": "fixtures/bad.yaml", "patched_path": "patches/bad.yaml"}),
                ],
            ),
            FakeResponse("end_turn", [FakeBlock("text", text="final summary")]),
        ]

        with patch.object(agent.client.messages, "create", side_effect=responses) as create_mock, patch.object(
            agent, "run_tool", side_effect=[{"patched_path": "patches/bad.yaml", "diff": "diff"}, {"resolved": [("CKV", "res")], "remaining": [], "new": []}]
        ) as run_tool_mock:
            result = agent.review("fixtures/bad.yaml", max_fix_attempts=2)

        self.assertEqual(result, "final summary")
        self.assertEqual(run_tool_mock.call_count, 2)
        texts = self._message_texts(create_mock)
        self.assertTrue(any("succeeded on attempt 1" in text for text in texts))

    def test_stops_after_max_failed_attempts(self):
        responses = [
            FakeResponse(
                "tool_use",
                [
                    FakeBlock("tool_use", id="patch-1", name="propose_patch", input={"path": "fixtures/bad.yaml", "fixed_content": "fixed-1"}),
                    FakeBlock("tool_use", id="validate-1", name="validate_patch", input={"original_path": "fixtures/bad.yaml", "patched_path": "patches/bad.yaml"}),
                ],
            ),
            FakeResponse(
                "tool_use",
                [
                    FakeBlock("tool_use", id="patch-2", name="propose_patch", input={"path": "patches/bad.yaml", "fixed_content": "fixed-2"}),
                    FakeBlock("tool_use", id="validate-2", name="validate_patch", input={"original_path": "fixtures/bad.yaml", "patched_path": "patches/bad.yaml"}),
                ],
            ),
            FakeResponse(
                "tool_use",
                [
                    FakeBlock("tool_use", id="patch-3", name="propose_patch", input={"path": "patches/bad.yaml", "fixed_content": "fixed-3"}),
                ],
            ),
            FakeResponse("end_turn", [FakeBlock("text", text="gave up cleanly")]),
        ]

        tool_results = [
            {"patched_path": "patches/bad.yaml", "diff": "diff-1"},
            {"resolved": [], "remaining": [("CKV", "res")], "new": []},
            {"patched_path": "patches/bad.yaml", "diff": "diff-2"},
            {"resolved": [], "remaining": [("CKV", "res")], "new": [("NEW", "res")]},
        ]

        with patch.object(agent.client.messages, "create", side_effect=responses) as create_mock, patch.object(
            agent, "run_tool", side_effect=tool_results
        ) as run_tool_mock:
            result = agent.review("fixtures/bad.yaml", max_fix_attempts=2)

        self.assertEqual(result, "gave up cleanly")
        self.assertEqual(run_tool_mock.call_count, 4)
        texts = self._message_texts(create_mock)
        self.assertTrue(any("Attempts left: 1" in text for text in texts))
        self.assertTrue(any("after 2 attempts" in text for text in texts))


if __name__ == "__main__":
    unittest.main()