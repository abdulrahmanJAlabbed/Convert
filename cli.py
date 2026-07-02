import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from pathlib import Path
from core.dispatcher import dispatch_conversion
import sys

app = typer.Typer(
    name="transcripe",
    help="Award-Winning Universal Semantic File Converter",
    add_completion=False,
    invoke_without_command=True
)
console = Console()

@app.callback()
def main(
    ctx: typer.Context,
    input_path: str = typer.Argument(
        None,
        help="Path to the file or directory to convert"
    ),
    to: str = typer.Option(
        None,
        "--to",
        "-t",
        help="Target format (e.g., txt, srt, pdf, md). If omitted, interactive mode launches."
    ),
):
    """
    Smart convert a file. 
    If you run without arguments, an interactive wizard will guide you through importing and exporting.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Beautiful welcome header
    console.print(Panel(
        "[bold blue]Transcripe[/bold blue] 🚀\n[dim]The Universal Semantic File Converter[/dim]",
        title="Welcome",
        expand=False
    ))

    # FULLY INTERACTIVE MODE: Ask for input path if missing
    if not input_path:
        input_path = Prompt.ask("\n[bold green]?[/bold green] Please enter the path to the file you want to convert (Import)")
        if not input_path:
            console.print("[red]No file provided. Exiting.[/red]")
            raise typer.Exit()

    file_path = Path(input_path).expanduser().resolve()
    
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] Cannot find file at '{file_path}'")
        raise typer.Exit(code=1)

    console.print(f"\nAnalyzing: [bold cyan]{file_path.name}[/bold cyan]")
    
    try:
        dispatch_conversion(file_path, to, console)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
