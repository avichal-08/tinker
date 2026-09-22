import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from src.agent.loop import run_diagnostic

app = typer.Typer(help="Tinker: Local-first AI agent for system maintenance.")
console = Console()


def get_ui_callbacks(status):

    def update_status(tool_name: str):
        friendly_names = {
            "get_system_stats": "system pressure",
            "get_top_processes": "top processes",
            "get_disk_usage": "primary disk space",
            "scan_developer_caches": "developer caches & temp files",
            "scan_docker_bloat": "Docker bloat",
            "scan_windows_bloat": "Windows system bloat",
            "scan_project_artifacts": "local project artifacts",
            "get_listening_ports": "open network ports",
            "clean_cache": "executing safe cleanup",
            "terminate_process": "terminating process",
            "get_power_and_thermal_stats": "power and thermal sensors",
        }
        name = friendly_names.get(tool_name, tool_name)
        status.update(f"[bold yellow]Inspecting {name}...")

    def ask_permission(name: str, size_mb: float, risk: str) -> bool:
        status.stop()
        console.print(
            "\n[bold red] ACTION REQUIRED: The agent wants to move files to the Recycle Bin or kill a process.[/bold red]"
        )
        console.print(f"Target: [bold]{name}[/bold]")
        console.print(f"Expected recovery: [bold green]{size_mb} MB[/bold green]")
        console.print(f"Risk Level: [bold yellow]{risk}[/bold yellow]\n")

        approved = Confirm.ask(
            "[bold red]Do you want to proceed?[/bold red]", default=False
        )

        status.start()
        if approved:
            status.update(f"[bold red]Executing {name}...[/bold red]")
        return approved

    return update_status, ask_permission


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
        update_status, ask_permission = get_ui_callbacks(status)

        diagnosis, _ = run_diagnostic(
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


@app.command()
def chat():
    console.print(
        Panel.fit(
            "[bold cyan]TINKER INTERACTIVE MODE[/bold cyan]\n[dim]Type 'exit' or 'quit' to end the session.[/dim]",
            border_style="cyan",
        )
    )

    chat_history = None

    while True:
        query = Prompt.ask("\n[bold blue]You[/bold blue]")
        if query.lower() in ["exit", "quit"]:
            console.print("[dim]Shutting down Tinker...[/dim]")
            break

        with console.status("[bold green]Thinking...", spinner="dots") as status:
            update_status, ask_permission = get_ui_callbacks(status)

            response, chat_history = run_diagnostic(
                query,
                on_tool_call=update_status,
                on_approval=ask_permission,
                chat_history=chat_history,
            )

        console.print(
            Panel(
                Markdown(response),
                title="[bold green]Tinker[/bold green]",
                border_style="green",
            )
        )


if __name__ == "__main__":
    app()
