import sys
import re
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(add_completion=False)

SEVERITY_COLORS = {
    "CRITICAL": typer.colors.RED,
    "HIGH": typer.colors.MAGENTA,
    "MEDIUM": typer.colors.YELLOW,
    "LOW": typer.colors.GREEN,
    "INFO": typer.colors.CYAN,
}
_SEVERITY_HEADING_RE = re.compile(
    r"^\s*#{1,6}\s*(?:\*\*)?(CRITICAL|HIGH|MEDIUM|LOW|INFO)(?:\s+ISSUES?)?(?:\*\*)?\s*:?\s*$",
    re.IGNORECASE,
)
_SEVERITY_LABEL_RE = re.compile(r"^\s*(?:\*\*)?(CRITICAL|HIGH|MEDIUM|LOW|INFO)(?:\*\*)?\s*:", re.IGNORECASE)


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _line_style(line: str) -> tuple[Any | None, bool]:
    stripped = line.strip()
    if not stripped:
        return None, False

    if stripped.startswith("#") and "review" in stripped.lower():
        return typer.colors.BRIGHT_WHITE, True

    severity_match = _SEVERITY_HEADING_RE.match(stripped) or _SEVERITY_LABEL_RE.match(stripped)
    if severity_match:
        severity = severity_match.group(1).upper()
        return SEVERITY_COLORS[severity], True

    if stripped.startswith("Control:") or stripped.startswith("- Control:"):
        return typer.colors.CYAN, False

    return None, False


def _emit_review_output(result: str) -> None:
    if not _supports_color():
        typer.echo(result)
        return

    for line in result.splitlines():
        fg, bold = _line_style(line)
        if fg is None:
            typer.echo(line)
            continue
        typer.secho(line, fg=fg, bold=bold)


@app.command(name="review")
def review_command(
    path: Path | None = typer.Argument(None, exists=True, resolve_path=True, help="File or directory to review."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write the review report to a file."),
    max_fix_attempts: int = typer.Option(
        3,
        "--max-fix-attempts",
        min=1,
        help="Maximum remediation retries before the agent stops patching.",
    ),
):
    """Review IaC/K8s files at PATH for security issues."""
    if path is None:
        raise typer.BadParameter("PATH is required when running the review command.")

    from agent import review

    result = review(str(path), max_fix_attempts=max_fix_attempts)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result, encoding="utf-8")

    _emit_review_output(result)

@app.command()
def evaluate():
    """Run the evaluation harness and print metrics."""
    from eval import eval_detection, eval_remediation

    typer.echo(f"Detection: {eval_detection()}")

    try:
        typer.echo(f"Remediation: {eval_remediation()}")
    except ModuleNotFoundError as exc:
        if exc.name == "anthropic":
            typer.echo("Remediation: unavailable (install 'anthropic' to run agent-based remediation evaluation)")
            return
        raise


def run() -> None:
    command_names = {
        command.name or command.callback.__name__.replace("_command", "").replace("_", "-")
        for command in app.registered_commands
    }
    args = sys.argv[1:]

    if args and not args[0].startswith("-") and args[0] not in command_names:
        sys.argv.insert(1, "review")

    app()


def run_evaluate() -> None:
    evaluate()


if __name__ == "__main__":
    run()
