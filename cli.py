import sys
from pathlib import Path

import typer

app = typer.Typer(add_completion=False)


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

    typer.echo(result)

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
