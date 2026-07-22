import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.align import Align
from rich.rule import Rule
from rich import box
import questionary
from questionary import Style
from pathlib import Path
import time
import sys
import os
import subprocess

from transcripe.core.dispatcher import (
    dispatch_conversion,
    dispatch_merge,
    get_file_category,
    UserCancelled,
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

# Non-interactive subcommands (transcripe convert/pdf/media/image/data/archive/model…)
from transcripe import commands as _commands
_commands.register(app)

# ── Helpers ────────────────────────────────────────────────────────────────

def _gradient_text(lines, start=(199, 60, 255), end=(0, 229, 255)) -> Text:
    """Render lines of text with a vertical color gradient (magenta → cyan)."""
    t = Text(justify="center")
    n = max(len(lines) - 1, 1)
    for i, line in enumerate(lines):
        r = int(start[0] + (end[0] - start[0]) * i / n)
        g = int(start[1] + (end[1] - start[1]) * i / n)
        b = int(start[2] + (end[2] - start[2]) * i / n)
        t.append(line + "\n", style=f"bold #{r:02x}{g:02x}{b:02x}")
    return t


def _spin(message: str, spinner: str = "dots"):
    """A themed spinner context manager for long-running steps."""
    return console.status(f"[bold cyan]{message}[/bold cyan]", spinner=spinner)


def _open_folder(path: Path):
    """Open a folder in the OS file manager."""
    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception:
        console.print(f"[dim]Could not open {path}[/dim]")


def _offer_open_folder(dirs: set):
    """Ask the user whether to reveal the output folder(s) in their file manager."""
    dirs = {Path(d) for d in dirs if d}
    if not dirs:
        return
    open_it = questionary.confirm(
        "📂  Open the output folder now?",
        default=False,
        style=THEME,
    ).ask()
    if open_it:
        for d in dirs:
            _open_folder(d)


def _print_banner():
    """Print the big animated app-name banner at the top."""
    width = console.width
    font = "ansi_shadow" if width >= 80 else "small"

    try:
        import pyfiglet
        art = pyfiglet.figlet_format("Transcripe", font=font).rstrip("\n")
        lines = [ln for ln in art.split("\n") if ln.strip()]
    except Exception:
        lines = ["⚡ TRANSCRIPE ⚡"]

    console.print()
    console.print(Align.center(_gradient_text(lines)))
    console.print(Align.center(
        Text("The Universal Semantic File Converter & Merger", style="italic bright_white")
    ))
    console.print(Align.center(
        Text("Convert  •  Merge  •  Extract  •  Transcribe  •  100% Local", style="dim")
    ))
    console.print(Rule(style="magenta"))


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
    """Use the C-optimized system 'find' command to search fast.

    Argument-list invocation (no shell) so filenames with quotes/;/$ are safe.
    """
    home = str(Path.home())
    if sys.platform == "win32":
        cmd = ["where", "/r", home, f"*{filename}*"]
    else:
        cmd = ["find", home, "-not", "-path", "*/.*", "-iname", f"*{filename}*"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return [m for m in result.stdout.strip().split("\n") if m][:25]
    except Exception:
        return []


def _add_path(fp: Path, files: list[Path], console) -> None:
    """Add a file (or a folder's supported files) to the selection, skipping duplicates."""
    if fp.is_dir():
        added = 0
        for child in fp.iterdir():
            if child.is_file() and child.suffix.lower() in ALL_SUPPORTED_EXTS and child not in files:
                files.append(child)
                added += 1
        console.print(f"[green]Added {added} supported files from {fp.name}/[/green]")
    elif fp in files:
        console.print(f"[dim]Already selected: {fp.name}[/dim]")
    else:
        files.append(fp)
        console.print(f"[green]+ {fp.name}[/green]")


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
            if not mode:
                continue
            is_folder = "Folder" in mode
            paths = _open_native_browser(multi=not is_folder, folder=is_folder)

            for p in paths:
                fp = Path(p).expanduser().resolve()
                if fp.exists():
                    _add_path(fp, files, console)
                else:
                    console.print(f"[red]Not found: {p}[/red]")
            continue

        if "Drag" in action:
            raw = questionary.path("Type or Drag & Drop your file/folder here:", style=THEME).ask()
            if raw:
                fp = Path(str(raw).strip().strip("'\"").strip()).expanduser().resolve()
                if fp.exists():
                    _add_path(fp, files, console)
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
                    _add_path(fp, files, console)

    return files


# ── Main CLI Entry ─────────────────────────────────────────────────────────

@app.callback()
def main(
    ctx: typer.Context,
    doctor: bool = typer.Option(False, "--doctor", help="Show environment & capabilities, then exit"),
    self_test: bool = typer.Option(False, "--self-test", help="Run conversion self-tests, then exit"),
    slow: bool = typer.Option(False, "--slow", help="Include slow self-tests (transcription pipeline)"),
):
    """
    🚀 Transcripe – The Universal Semantic File Converter & Merger.

    Run without arguments for a fully interactive wizard, or use a subcommand
    (convert, pdf, media, image, data, archive, model) for scripting.
    `transcripe FILE --to FMT` still works as a shortcut for `convert`.
    """
    if ctx.invoked_subcommand is not None:
        return

    # ── Doctor / self-test mode ────────────────────────────────────────
    if doctor or self_test:
        _print_banner()
        from transcripe.core import doctor as doctor_mod
        failures = doctor_mod.run(console, do_selftest=self_test, include_slow=slow)
        raise typer.Exit(code=1 if failures else 0)

    _print_banner()

    # ── Fully interactive wizard ───────────────────────────────────────
    with _spin("Waking up the conversion agent…", spinner="aesthetic"):
        time.sleep(0.6)

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
    result_dirs = set()
    if is_merge:
        console.print(
            "\n[bold bright_cyan]Step 2:[/bold bright_cyan] "
            "[white]Configure your merge[/white]\n"
        )
        try:
            result_dirs = dispatch_merge(files, console) or set()
        except UserCancelled:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit()
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)
    else:
        console.print(
            "\n[bold bright_cyan]Step 2:[/bold bright_cyan] "
            "[white]Choose output format[/white]\n"
        )
        try:
            result_dirs = dispatch_conversion(files, None, console) or set()
        except UserCancelled:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit()
        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)

    # Offer to open the output folder(s)
    _offer_open_folder(result_dirs)

    # Final
    console.print(Panel(
        "[bold green]All done! 🎉[/bold green]\n"
        "[dim]Run [bold]transcripe[/bold] again anytime.[/dim]",
        border_style="green",
        box=box.ROUNDED,
        expand=False,
        padding=(1, 3),
    ))


def main_entry():
    """Console entry point with a legacy shim:

    `transcripe file.mp4 --to srt` (old direct mode) is rewritten to
    `transcripe convert file.mp4 --to srt` so both styles keep working.
    """
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        first = sys.argv[1]
        if first not in _commands.SUBCOMMANDS and Path(first).expanduser().exists():
            sys.argv.insert(1, "convert")
    app()


if __name__ == "__main__":
    main_entry()
