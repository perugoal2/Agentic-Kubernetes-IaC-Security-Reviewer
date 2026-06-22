import unittest
from unittest.mock import patch

import cli


class CliOutputTests(unittest.TestCase):
    def test_emit_review_output_colorizes_severity_headings(self):
        report = """## IaC Security Review Report

## CRITICAL
- Finding: Privileged container
- Control: CIS 5.2.1

## HIGH
- Finding: Missing limits
"""

        with patch("cli._supports_color", return_value=True), patch("cli.typer.echo") as echo_mock, patch(
            "cli.typer.secho"
        ) as secho_mock:
            cli._emit_review_output(report)

        secho_calls = [call.args[0] for call in secho_mock.call_args_list]
        self.assertIn("## IaC Security Review Report", secho_calls)
        self.assertIn("## CRITICAL", secho_calls)
        self.assertIn("## HIGH", secho_calls)

        control_call = next(call for call in secho_mock.call_args_list if call.args[0] == "- Control: CIS 5.2.1")
        self.assertEqual(control_call.kwargs["fg"], cli.typer.colors.CYAN)
        self.assertFalse(control_call.kwargs["bold"])

        critical_call = next(call for call in secho_mock.call_args_list if call.args[0] == "## CRITICAL")
        self.assertEqual(critical_call.kwargs["fg"], cli.typer.colors.RED)
        self.assertTrue(critical_call.kwargs["bold"])

        echo_calls = [call.args[0] for call in echo_mock.call_args_list if call.args]
        self.assertIn("- Finding: Privileged container", echo_calls)

    def test_emit_review_output_falls_back_to_plain_text_without_color(self):
        report = "## HIGH\n- Finding: Missing limits"

        with patch("cli._supports_color", return_value=False), patch("cli.typer.echo") as echo_mock, patch(
            "cli.typer.secho"
        ) as secho_mock:
            cli._emit_review_output(report)

        echo_mock.assert_called_once_with(report)
        secho_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()