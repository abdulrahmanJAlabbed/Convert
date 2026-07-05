import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich import box
import questionary
from questionary import Style
from pathlib import Path
import sys
import os
import subprocess

from core.dispatcher import (
    dispatch_conversion,
    dispatch_merge,
    get_file_category,
    ALL_SUPPORTED_EXTS,
    VIDEO_EXTS, AUDIO_EXTS, DOC_EXTS, DATA_EXTS, IMAGE_EXTS,
)

# ── Questionary custom theme (award-winning CLI look) ──────────────────────
THEME = Style([
    ("qmark",       "fg:#673ab7 bold"),      # the ? mark
    ("question",    "fg:#ffffff bold"),       # question text
    ("answer",      "fg:#00e676 bold"),       # submitted answer
    ("pointer",     "fg:#673ab7 bold"),       # the > pointer
    ("highlighted", "fg:#673ab7 bold"),       # highlighted choice
    ("selected",    "fg:#00e676"),            # selected in checkbox
    ("separator",   "fg:#757575"),
    ("instruction", "fg:#9e9e9e"),
])

app = typer.Typer(
    name="transcripe",
    help="🚀 The Universal Semantic File Converter & Merger",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()

# ── Helpers ────────────────────────────────────────────────────────────────

def _print_banner():
    """Print the beautiful welcome banner."""
    console.print()
    console.print(Panel(
        "[bold bright_magenta]⚡ Transcripe[/bold bright_magenta]\n"
        "[dim white]The Universal Semantic File Converter & Merger[/dim white]\n"
        "[dim]Convert • Merge • Extract • Transform[/dim]",
        border_style="bright_magenta",
        box=box.DOUBLE_EDGE,
        expand=False,
        padding=(1, 4),
    ))


def _print_supported_formats():
    """Print a pretty table of all supported formats."""
    table = Table(
        title="Supported Formats",
        box=box.ROUNDED,
        border_style="dim",
        title_style="bold bright_cyan",
        show_lines=True,
    )
    table.add_column("Category", style="bold yellow", width=14)
    table.add_column("Extensions", style="cyan")
    table.add_column("Actions", style="green")

    table.add_row(
        "🎬 Video",
        ", ".join(sorted(VIDEO_EXTS)),
        "Transcribe → .txt / .srt\nExtract Audio → .mp3 .wav .flac\nConvert → .mp4 .mkv .webm\n→ GIF / Compress / Trim / Frames",
    )
    table.add_row(
        "🎵 Audio",
        ", ".join(sorted(AUDIO_EXTS)),
        "Transcribe → .txt / .srt\nConvert → .mp3 .wav .flac .ogg .aac",
    )
    table.add_row(
        "📄 Document",
        ", ".join(sorted(DOC_EXTS)),
        "Convert → .pdf / .md / .docx / .html / .txt",
    )
    table.add_row(
        "📊 Data",
        ", ".join(sorted(DATA_EXTS)),
        "CSV ↔ JSON ↔ YAML\nExcel → CSV / JSON\nJSON prettify / minify",
    )
    table.add_row(
        "🖼️  Image",
        ", ".join(sorted(IMAGE_EXTS)),
        "OCR → .txt\nConvert → .png .webp .jpg\nResize / Compress / → PDF",
    )
    table.add_row(
        "📕 PDF",
        ".pdf",
        "Extract Text / Pages → Images\nSplit Pages / → .md .html .docx",
    )
    console.print(table)


def _open_native_browser(multi=False, folder=False):
    """Open a modern native file browser. Returns a path string or list of paths."""
    try:
        if sys.platform.startswith("linux") and subprocess.run(
            ["which", "zenity"], capture_output=True
        ).returncode == 0:
            cmd = ["zenity", "--file-selection", "--title=Transcripe – Select Files"]
            if folder:
                cmd.append("--directory")
            if multi:
                cmd.append("--multiple")
                cmd.append("--separator=|")
            result = subprocess.run(cmd, capture_output=True, text=True)
            raw = result.stdout.strip()
            if not raw:
                return []
            return raw.split("|") if multi else [raw]
        else:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            if folder:
                path = filedialog.askdirectory(title="Select Folder")
                root.destroy()
                return [path] if path else []
            elif multi:
                paths = filedialog.askopenfilenames(title="Select Files")
                root.destroy()
                return list(paths) if paths else []
            else:
                path = filedialog.askopenfilename(title="Select File")
                root.destroy()
                return [path] if path else []
    except Exception:
        console.print("[red]Native browser unavailable. Falling back to typing.[/red]")
        p = questionary.path("Type or Drag & Drop your file here:", style=THEME).ask()
        return [p] if p else []


def _turbo_search(filename: str) -> list[str]:
    """Use the C-optimized system 'find' command to search fast."""
    home = str(Path.home())
    if sys.platform == "win32":
        cmd = f'where /r "{home}" "*{filename}*" 2>NUL'
    else:
        cmd = f'find {home} -not -path "*/\\.*" -iname "*{filename}*" 2>/dev/null | head -n 25'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        return [m for m in result.stdout.strip().split("\n") if m]
    except Exception:
        return []


def _collect_files() -> list[Path]:
    """The main interactive file collection flow. Returns a list of validated Path objects."""
    files: list[Path] = []

    while True:
        action = questionary.select(
            "How would you like to find your files?",
            choices=[
                "🪟  Open Native File Browser (supports multi-select)",
                "📥  Type or Drag & Drop a Path",
                "⚡  Turbo Search by Name",
                "📋  View Selected Files So Far",
                "✅  Done – Proceed with selected files",
                "❌  Exit",
            ],
            style=THEME,
        ).ask()

        if not action or "Exit" in action:
            raise typer.Exit()

        if "Done" in action:
            if not files:
                console.print("[yellow]You haven't selected any files yet.[/yellow]")
                continue
            break

        if "View" in action:
            if not files:
                console.print("[dim]No files selected yet.[/dim]")
            else:
                table = Table(box=box.SIMPLE_HEAD, border_style="dim")
                table.add_column("#", style="dim", width=4)
                table.add_column("File", style="cyan")
                table.add_column("Type", style="yellow")
                table.add_column("Size", style="green")
                for i, f in enumerate(files, 1):
                    cat = get_file_category(f)
                    size = f.stat().st_size
                    size_str = f"{size / 1024:.1f} KB" if size < 1_048_576 else f"{size / 1_048_576:.1f} MB"
                    table.add_row(str(i), f.name, cat, size_str)
                console.print(table)
            continue

        if "Browser" in action:
            mode = questionary.select(
                "What would you like to select?",
                choices=["📄 File(s)", "📁 Folder"],
                style=THEME,
            ).ask()
            is_folder = "Folder" in mode
            paths = _open_native_browser(multi=not is_folder, folder=is_folder)

            for p in paths:
                fp = Path(p).expanduser().resolve()
                if fp.exists():
                    if fp.is_dir():
                        added = 0
                        for child in fp.iterdir():
                            if child.is_file() and child.suffix.lower() in ALL_SUPPORTED_EXTS:
                                files.append(child)
                                added += 1
                        console.print(f"[green]Added {added} supported files from {fp.name}/[/green]")
                    else:
                        files.append(fp)
                        console.print(f"[green]+ {fp.name}[/green]")
                else:
                    console.print(f"[red]Not found: {p}[/red]")
            continue

        if "Drag" in action:
            raw = questionary.path("Type or Drag & Drop your file/folder here:", style=THEME).ask()
            if raw:
                fp = Path(str(raw).strip().strip("'\"").strip()).expanduser().resolve()
                if fp.exists():
                    if fp.is_dir():
                        added = 0
                        for child in fp.iterdir():
                            if child.is_file() and child.suffix.lower() in ALL_SUPPORTED_EXTS:
                                files.append(child)
                                added += 1
                        console.print(f"[green]Added {added} supported files from {fp.name}/[/green]")
                    else:
                        files.append(fp)
                        console.print(f"[green]+ {fp.name}[/green]")
                else:
                    console.print(f"[red]Cannot find: {fp}[/red]")
            continue

        if "Search" in action:
            filename = questionary.text("What is the name of the file (or part of it)?", style=THEME).ask()
            if not filename:
                continue
            console.print(f"[dim]⚡ Searching your home directory...[/dim]")
            matches = _turbo_search(filename)

            if not matches:
                console.print(f"[red]No results for '{filename}'.[/red]")
                continue

            selected = questionary.checkbox(
                "Select files to add (Space to toggle, Enter to confirm):",
                choices=matches,
                style=THEME,
            ).ask()

            for s in (selected or []):
                fp = Path(s).expanduser().resolve()
                if fp.exists():
                    files.append(fp)
                    console.print(f"[green]+ {fp.name}[/green]")

    return files


# ── Main CLI Entry ─────────────────────────────────────────────────────────

@app.callback()
def main(
    ctx: typer.Context,
    input_path: str = typer.Argument(None, help="Path to a file or directory to convert"),
    to: str = typer.Option(None, "--to", "-t", help="Target format (txt, srt, pdf, md, webp…)"),
):
    """
    🚀 Transcripe – The Universal Semantic File Converter & Merger.

    Run without arguments for a fully interactive wizard.
    """
    if ctx.invoked_subcommand is not None:
        return

    _print_banner()

    # ── Direct CLI mode (e.g. transcripe video.mp4 --to srt) ───────────
    if input_path:
        fp = Path(input_path).expanduser().resolve()
        if not fp.exists():
            console.print(f"[bold red]Error:[/bold red] Cannot find '{fp}'")
            raise typer.Exit(code=1)
        console.print(f"\n[bold magenta]🤖 Agent:[/bold magenta] Analyzing [cyan]{fp.name}[/cyan]…")
        try:
            dispatch_conversion([fp], to, console)
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)
        return

    # ── Fully interactive wizard ───────────────────────────────────────
    console.print(
        "\n[bold magenta]🤖 Agent Transcripe:[/bold magenta] "
        "Hello! I'm your Universal Conversion Agent.\n"
        "[dim]   I can convert, merge, extract text, transcribe, and more.[/dim]\n"
    )

    # Step 1 — What do you want to do?
    task = questionary.select(
        "What would you like to do?",
        choices=[
            "🔄  Convert file(s)",
            "🔗  Merge files together",
            "📋  View supported formats",
            "❌  Exit",
        ],
        style=THEME,
    ).ask()

    if not task or "Exit" in task:
        console.print("[dim]Goodbye![/dim]")
        raise typer.Exit()

    if "formats" in task.lower():
        _print_supported_formats()
        raise typer.Exit()

    is_merge = "Merge" in task

    # Step 2 — Collect files
    console.print(
        "\n[bold bright_cyan]Step 1:[/bold bright_cyan] "
        "[white]Select your files[/white]\n"
        "[dim]You can add multiple files from different locations. "
        "When done, select '✅ Done'.[/dim]\n"
    )
    files = _collect_files()

    # Summary of selected files
    console.print(f"\n[bold green]✓ {len(files)} file(s) selected.[/bold green]")

    # Step 3 — Merge or Convert
    if is_merge:
        console.print(
            "\n[bold bright_cyan]Step 2:[/bold bright_cyan] "
            "[white]Configure your merge[/white]\n"
        )
        try:
            dispatch_merge(files, console)
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)
    else:
        console.print(
            "\n[bold bright_cyan]Step 2:[/bold bright_cyan] "
            "[white]Choose output format[/white]\n"
        )
        try:
            dispatch_conversion(files, None, console)
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)

    # Final
    console.print(Panel(
        "[bold green]All done! 🎉[/bold green]\n"
        "[dim]Run [bold]transcripe[/bold] again anytime.[/dim]",
        border_style="green",
        box=box.ROUNDED,
        expand=False,
        padding=(1, 3),
    ))


if __name__ == "__main__":
    app()
