from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

console = Console()

RISK_STYLES = {
    "safe": "green",
    "caution": "yellow",
    "dangerous": "red",
    "blocked": "bold red",
}


def show_banner(url: str, thread_id: str) -> None:
    console.print(
        Panel(
            Text.assemble(
                ("Terminal Agent\n", "bold cyan"),
                (f"server  {url}\n", "dim"),
                (f"session {thread_id}", "dim"),
            ),
            border_style="cyan",
        )
    )
    console.print("Type your request, or [bold]exit[/bold] to quit.\n", style="dim")


def prompt_user() -> str:
    return console.input("[bold cyan]you[/bold cyan] ")


def start_reply() -> None:
    console.print("[bold green]agent[/bold green] ", end="")


def write_token(text: str) -> None:
    console.print(text, end="", markup=False, highlight=False)


def finish_reply(text: str, streamed: bool) -> None:
    if streamed:
        console.print("\n")
        return

    console.print()
    console.print(Markdown(text) if text else "[dim](no reply)[/dim]")
    console.print()


def show_error(message: str) -> None:
    console.print(f"[bold red]error[/bold red] {message}\n")


def ask_approval(request: dict) -> bool:
    calls = request.get("calls", [])
    if not calls:
        return False

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("risk")
    table.add_column("command")
    table.add_column("why")

    for call in calls:
        risk = call.get("risk", "caution")
        table.add_row(
            Text(risk.upper(), style=RISK_STYLES.get(risk, "yellow")),
            Text(call.get("command", ""), style="bold"),
            Text(call.get("reason", ""), style="dim"),
        )

    highest = _highest_risk(calls)
    console.print()
    console.print(
        Panel(table, title="approval needed", border_style=RISK_STYLES.get(highest, "yellow"))
    )

    return Confirm.ask("[bold]run it?[/bold]", default=False)


def _highest_risk(calls: list[dict]) -> str:
    for level in ("blocked", "dangerous", "caution", "safe"):
        if any(call.get("risk") == level for call in calls):
            return level
    return "caution"
