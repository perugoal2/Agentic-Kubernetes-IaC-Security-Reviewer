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

import eval as eval_module
import agent


class EvalTests(unittest.TestCase):
    def test_eval_detection_counts_tp_fp_fn(self):
        ground_truth = {
            "fixtures/a.yaml": ["CKV_A", "KSV_A", "KSV_B"],
            "fixtures/b.yaml": ["CKV_C"],
        }
        scan_findings = [
            [{"id": "CKV_A"}, {"id": "KSV_A"}, {"id": "CKV_X"}],
            [],
        ]

        with patch("builtins.open", create=True), patch.object(eval_module.json, "load", return_value=ground_truth), patch.object(
            eval_module, "scan_findings", side_effect=scan_findings
        ):
            result = eval_module.eval_detection()

        self.assertEqual(result, {"detection_rate": 0.5, "false_positive_rate": 0.333, "tp": 2, "fp": 1, "fn": 2})

    def test_eval_remediation_counts_fully_resolved_patches(self):
        ground_truth = {
            "fixtures/a.yaml": ["CKV_A"],
            "fixtures/b.yaml": ["CKV_B"],
            "fixtures/c.yaml": ["CKV_C"],
        }

        with patch("builtins.open", create=True), patch.object(eval_module.json, "load", return_value=ground_truth), patch.object(
            agent, "remediate", side_effect=["patches/a.yaml", None, "patches/c.yaml"]
        ), patch.object(
            eval_module,
            "validate_patch",
            side_effect=[
                {"remaining": [], "new": []},
                {"remaining": [("CKV_C", "res")], "new": []},
            ],
        ):
            result = eval_module.eval_remediation()

        self.assertEqual(result, {"remediation_validity": 0.5, "patched": 2, "fully_resolved": 1})


if __name__ == "__main__":
    unittest.main()