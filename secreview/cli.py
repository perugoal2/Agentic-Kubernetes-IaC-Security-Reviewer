import typer
app = typer.Typer();

@app.command()
def main(path: str):
    """Review IaC/K8s files at PATH for security issues."""
    typer.echo(f"Reviewing {path} ...")

if __name__ == "__main__":
    app()
