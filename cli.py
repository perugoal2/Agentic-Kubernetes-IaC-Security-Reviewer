from pathlib import Path

import typer

from agent import review

app = typer.Typer(add_completion=False)


@app.command()
def main(
    path: Path = typer.Argument(..., exists=True, resolve_path=True, help="File or directory to review."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write the review report to a file."),
):
    """Review IaC/K8s files at PATH for security issues."""
    result = review(str(path))

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result, encoding="utf-8")

    typer.echo(result)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
