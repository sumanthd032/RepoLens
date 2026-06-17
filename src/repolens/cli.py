"""RepoLens command-line interface.

Thin typer wrapper over the same engine the server uses: ``index`` runs the ingestion pipeline,
``ask`` runs the grounded answer flow and prints it with citations, ``drift`` prints the drift
report (and powers CI via ``--ci``), and ``serve`` starts the FastAPI server.
"""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.panel import Panel

from repolens.api.engine import answer_events, build_state, run_drift
from repolens.utils.logger import get_logger

logger = get_logger("cli")
app = typer.Typer(
    help="RepoLens — grounded code Q&A and doc-drift detection.", no_args_is_help=True
)
console = Console()


@app.command()
def index(
    path: str = typer.Argument(..., help="Path to the repository to index."),
    name: str = typer.Option(None, "--name", "-n", help="Display name for the repo."),
) -> None:
    """Index a repository on disk."""
    state = build_state()
    with console.status(f"Indexing {path} ..."):
        result = state.pipeline.index(path, name=name)
    console.print(
        Panel.fit(
            f"[bold]{result.name}[/bold]  (id: {result.repo_id})\n"
            f"files: {result.num_files}   chunks: {result.num_chunks}\n"
            f"languages: {', '.join(result.languages) or '—'}",
            title="✓ Indexed",
            border_style="green",
        )
    )


@app.command()
def ask(
    query: str = typer.Argument(..., help="Question to ask about the repository."),
    repo: str = typer.Option(..., "--repo", "-r", help="Repo id to query."),
) -> None:
    """Ask a grounded question about an indexed repository."""
    state = build_state()
    record = state.metadata.get_repo(repo)
    if record is None:
        console.print(f"[red]Repo {repo!r} not found.[/red]")
        raise typer.Exit(1)

    async def run() -> None:
        citations: list[dict[str, object]] = []
        async for event in answer_events(state, record, query):
            kind, data = event["event"], json.loads(event["data"])
            if kind == "token":
                console.print(data["text"], end="")
            elif kind == "citation":
                citations.append(data)
            elif kind == "grounding":
                console.print(
                    f"\n\n[bold]Grounding:[/bold] {data['score']:.2f} ({data['verdict']})"
                )
            elif kind == "error":
                console.print(f"\n[red]{data['message']}[/red]")
        if citations:
            console.print("\n[bold]Citations:[/bold]")
            for c in citations:
                sym = f" ({c['symbol']})" if c.get("symbol") else ""
                console.print(f"  • {c['file']}:{c['start']}-{c['end']}{sym}")

    asyncio.run(run())


@app.command()
def drift(
    repo: str = typer.Option(..., "--repo", "-r", help="Repo id to check."),
    ci: bool = typer.Option(False, "--ci", help="Exit non-zero if drift is contradicted."),
) -> None:
    """Detect documentation drift for an indexed repository."""
    state = build_state()
    record = state.metadata.get_repo(repo)
    if record is None:
        console.print(f"[red]Repo {repo!r} not found.[/red]")
        raise typer.Exit(1)

    reporter = asyncio.run(run_drift(state, record))
    console.print(reporter.to_markdown())
    if ci and reporter.has_contradictions():
        console.print("[red]Drift detected: documentation contradicts code.[/red]")
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind."),
) -> None:
    """Start the RepoLens API + UI server."""
    import uvicorn

    uvicorn.run("repolens.server:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    app()
