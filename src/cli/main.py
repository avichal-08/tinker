import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm

from src.agent.loop import run_diagnostic

app = typer.Typer(
    help="Tinker: Local-first AI agent for system maintenance."
)
console = Console()


@app.command()
def diagnose(query: str = typer.Argument("Why is my computer slow?")):
    console.print(
        Panel.fit(
            f"[bold cyan]TINKER[/bold cyan]\n[dim]Query: {query}[/dim]",
            border_style="cyan",
        )
    )

    with console.status(
        "[bold green]Investigating system state...", spinner="dots"
    ) as status:

        def update_status(tool_name: str):
            friendly_names = {
                "get_system_stats": "system pressure",
                "get_top_processes": "top processes",
                "get_disk_usage": "primary disk space",
                "scan_developer_caches": "developer caches & temp files",
                "clean_cache": "executing safe cleanup",
                "terminate_process": "terminating process",
            }
            name = friendly_names.get(tool_name, tool_name)
            status.update(f"[bold yellow]Inspecting {name}...")

        def ask_permission(name: str, size_mb: float, risk: str) -> bool:
            status.stop()

            console.print(
                "\n[bold red] ACTION REQUIRED: The agent wants to delete files.[/bold red]"
            )
            console.print(f"Target: [bold]{name}[/bold]")
            console.print(f"Expected recovery: [bold green]{size_mb} MB[/bold green]")
            console.print(f"Risk Level: [bold yellow]{risk}[/bold yellow]\n")

            approved = Confirm.ask(
                "[bold red]Do you want to proceed with this deletion?[/bold red]",
                default=False,
            )

            status.start()
            if approved:
                status.update(f"[bold red]Sweeping {name}...[/bold red]")
            return approved

        diagnosis = run_diagnostic(
            query, on_tool_call=update_status, on_approval=ask_permission
        )

    console.print("\n")
    console.print(
        Panel(
            Markdown(diagnosis),
            title="[bold green]Final Report[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )


if __name__ == "__main__":
    app()
