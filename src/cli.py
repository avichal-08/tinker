import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent import run_diagnostic

app = typer.Typer(
    help="Computer Mechanic: Local-first AI agent for system maintenance."
)
console = Console()


@app.command()
def diagnose(query: str = typer.Argument("Why is my computer slow?")):
    console.print(
        Panel.fit(
            f"[bold cyan]COMPUTER MECHANIC[/bold cyan]\n[dim]Query: {query}[/dim]",
            border_style="cyan",
        )
    )

    with console.status(
        "[bold green]Investigating system state...", spinner="dots"
    ) as status:

        def update_status(tool_name: str):
            friendly_names = {
                "get_system_stats": "system pressure (CPU/RAM/Disk)",
                "get_top_processes": "top memory-consuming processes",
                "get_disk_usage": "primary disk space",
            }
            name = friendly_names.get(tool_name, tool_name)
            status.update(f"[bold yellow]Inspecting {name}...")

        diagnosis = run_diagnostic(query, on_tool_call=update_status)

    console.print("\n")
    console.print(
        Panel(
            Markdown(diagnosis),
            title="[bold green]Diagnosis & Recommendations[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


if __name__ == "__main__":
    app()
