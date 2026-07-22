"""Transcripe TUI — full-screen terminal front end (Textual).

Launch:  transcripe ui

Layout
    left   directory tree (browse anywhere, Enter/Space adds a file)
    right  selection table (file · type · size) + hints
Keys
    space/enter  add file (in tree) · c convert · x remove · C clear
    h            toggle hidden files · q quit
Flow
    pick files → press c → choose an action (filtered to the selection's
    category) → live dashboard: per-file status table + streaming engine log.

All conversions run in a worker thread with buffered consoles, so the UI never
blocks and engine output streams into the log pane.
"""
from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console
from rich.text import Text

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    DataTable, DirectoryTree, Footer, Header, Label, OptionList, RichLog, Static,
)
from textual.widgets.option_list import Option

from core.dispatcher import (
    ALL_SUPPORTED_EXTS, get_file_category, _get_ext_category, _human_size,
)

# ── action catalog ──────────────────────────────────────────────────────────
# Each action: (label, runner). Runner(file, console) → None, raises on error.
# Runners call engines directly with sane defaults — zero prompts.


def _std(fmt):
    """Standard-format runner via the dispatcher (capability-gated)."""
    def run(f: Path, console: Console):
        from core.dispatcher import _process_single_file
        _process_single_file(f, fmt, console, confirm_output=False)
    return run


def _call(fn_name, *args, **kwargs):
    """Direct engine call runner: 'module.function'."""
    def run(f: Path, console: Console):
        mod_name, func = fn_name.rsplit(".", 1)
        import importlib
        mod = importlib.import_module(mod_name)
        getattr(mod, func)(f, *args, console, **kwargs)
    return run


def _actions_for(cat: str) -> list[tuple[str, object]]:
    from core import capabilities
    A: list[tuple[str, object]] = []
    if cat in ("video", "audio"):
        A += [("📝 Transcribe → .txt", _std("txt")),
              ("🎬 Subtitles → .srt", _std("srt"))]
        if capabilities.can("transcribe"):
            A += [("🌐 Translate → English .txt",
                   lambda f, c: __import__("engines.audio_video", fromlist=["x"])
                   .transcribe(f, "txt", c, translate=True))]
        A += [("🎵 → .mp3", _std("mp3")), ("🎵 → .wav", _std("wav")),
              ("🎵 → .flac", _std("flac"))]
        if cat == "video":
            A += [("🎞  → GIF (10fps · 480px)",
                   lambda f, c: __import__("engines.audio_video", fromlist=["x"])
                   .video_to_gif(f, 10, 480, c)),
                  ("📦 Compress (medium)",
                   lambda f, c: __import__("engines.audio_video", fromlist=["x"])
                   .compress_video(f, "medium", c)),
                  ("🖼  Extract frames (1 fps)",
                   lambda f, c: __import__("engines.audio_video", fromlist=["x"])
                   .extract_frames(f, 1, c)),
                  ("🔄 → .mp4", _std("mp4")), ("🔄 → .webm", _std("webm"))]
    elif cat == "pdf":
        A += [("📝 Extract text → .txt", _std("txt")),
              ("✏️  Edit in browser (design kept)",
               lambda f, c: __import__("engines.pdf_edit", fromlist=["x"]).editable_html(f, c)),
              ("📄 → Word .docx (layout)", _std("docx")),
              ("📝 → Markdown .md", _std("md")),
              ("🖼  Pages → PNGs",
               lambda f, c: __import__("engines.documents", fromlist=["x"]).pdf_to_images(f, c)),
              ("🖼  Extract embedded images",
               lambda f, c: __import__("engines.pdf_edit", fromlist=["x"]).extract_images(f, None, c))]
        if capabilities.can("pdf_ocr"):
            A += [("🔎 OCR scanned PDF → .txt",
                   lambda f, c: __import__("engines.documents", fromlist=["x"]).pdf_ocr(f, c))]
        if capabilities.can("pdf_searchable"):
            A += [("🪄 Make searchable",
                   lambda f, c: __import__("engines.pdf_edit", fromlist=["x"]).make_searchable(f, c))]
    elif cat == "document":
        A += [("📕 → PDF", _std("pdf")), ("📝 → Markdown .md", _std("md")),
              ("🌐 → HTML", _std("html")), ("📄 → Word .docx", _std("docx")),
              ("📃 → Plain text .txt", _std("txt"))]
    elif cat == "image":
        A += [("📝 OCR → .txt", _std("txt")),
              ("🖼  → .png", _std("png")), ("🖼  → .webp", _std("webp")),
              ("🖼  → .jpg", _std("jpg")), ("📕 → PDF", _std("pdf")),
              ("📦 Compress (q60)",
               lambda f, c: __import__("engines.images", fromlist=["x"]).compress_image(f, 60, c))]
    elif cat == "data":
        A += [("📊 → .json", _std("json")), ("📊 → .csv", _std("csv")),
              ("📊 → .xlsx", _std("xlsx")), ("📊 → .parquet", _std("parquet")),
              ("📊 → .ndjson", _std("ndjson"))]
    elif cat == "subtitle":
        A += [("💬 → .srt", _std("srt")), ("💬 → .vtt", _std("vtt")),
              ("💬 → .ass", _std("ass")), ("📃 → .txt (strip timing)", _std("txt"))]
    elif cat == "archive":
        A += [("📂 Extract all",
               lambda f, c: __import__("engines.archive", fromlist=["x"]).extract(f, None, c))]
    elif cat == "model3d":
        A += [("🌐 Web GLB (Draco)",
               lambda f, c: __import__("engines.models3d", fromlist=["x"])
               .convert_model(f, "glb", c, optimize=True, compress="draco")),
              ("🧊 → .obj",
               lambda f, c: __import__("engines.models3d", fromlist=["x"])
               .convert_model(f, "obj", c, optimize=False)),
              ("🧊 → .stl",
               lambda f, c: __import__("engines.models3d", fromlist=["x"])
               .convert_model(f, "stl", c, optimize=False))]
    # Cross-category fallbacks for mixed selections
    if not A:
        A += [("📃 → Plain text .txt", _std("txt")), ("📕 → PDF", _std("pdf"))]
    return A


# ── widgets ─────────────────────────────────────────────────────────────────

class SupportedTree(DirectoryTree):
    """Directory tree that only shows folders + supported files."""

    show_hidden = False

    def filter_paths(self, paths):
        out = []
        for p in paths:
            if not self.show_hidden and p.name.startswith("."):
                continue
            if p.is_dir() or p.suffix.lower() in ALL_SUPPORTED_EXTS:
                out.append(p)
        return out


class ActionPicker(ModalScreen):
    """Modal: choose what to do with the current selection."""

    BINDINGS = [Binding("escape", "dismiss_none", "Cancel")]

    def __init__(self, category: str, n_files: int):
        super().__init__()
        self.category = category
        self.n_files = n_files
        self.actions = _actions_for(category)

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Label(f"  {self.n_files} file(s) · {self.category} — choose an action", id="picker-title")
            yield OptionList(*[Option(label, id=str(i)) for i, (label, _) in enumerate(self.actions)])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.actions[int(event.option.id)])

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


class RunScreen(Screen):
    """Live conversion dashboard: status table + streaming log."""

    BINDINGS = [Binding("escape,q", "go_back", "Back")]

    def __init__(self, files: list[Path], action_label: str, runner):
        super().__init__()
        self.files = files
        self.action_label = action_label
        self.runner = runner
        self.done = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(f"  ⚡ {self.action_label} — {len(self.files)} file(s)", id="run-title")
        yield DataTable(id="run-table")
        yield RichLog(id="run-log", wrap=True, highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#run-table", DataTable)
        self._col_status, self._col_file = table.add_columns("Status", "File")
        for f in self.files:
            table.add_row("⏳ queued", f.name, key=str(f))
        self._run_jobs()

    @work(thread=True)
    def _run_jobs(self) -> None:
        table = self.query_one("#run-table", DataTable)
        log = self.query_one("#run-log", RichLog)
        ok = fail = 0
        for f in self.files:
            self.app.call_from_thread(
                table.update_cell, str(f), self._col_status, "⚙ running")
            buf = Console(file=io.StringIO(), width=100, force_terminal=False)
            try:
                self.runner(f, buf)
                ok += 1
                status = Text("✓ done", style="bold green")
            except Exception as e:
                fail += 1
                status = Text("✗ failed", style="bold red")
                buf.print(f"[red]{type(e).__name__}: {e}[/red]")
            out = buf.file.getvalue().strip()
            self.app.call_from_thread(table.update_cell, str(f), self._col_status, status)
            if out:
                self.app.call_from_thread(log.write, f"── {f.name} " + "─" * 40)
                self.app.call_from_thread(log.write, out)
        self.done = True
        summary = Text(f"\n{ok} succeeded · {fail} failed — press Esc to go back",
                       style="bold green" if fail == 0 else "bold red")
        self.app.call_from_thread(log.write, summary)

    def action_go_back(self) -> None:
        self.app.pop_screen()


# ── main app ────────────────────────────────────────────────────────────────

class TranscripeTUI(App):
    TITLE = "Transcripe"
    SUB_TITLE = "Universal converter · PDF editor · 100% local"

    CSS = """
    #body { height: 1fr; }
    #tree-pane { width: 45%; border: round $primary; }
    #side-pane { width: 55%; }
    #sel-title { padding: 0 1; color: $text-muted; }
    #sel-table { height: 1fr; border: round $secondary; }
    #hints { padding: 0 1; color: $text-muted; }
    #picker { width: 64; max-height: 24; border: thick $primary; background: $surface; }
    #picker-title { padding: 1; text-style: bold; }
    #run-title { padding: 0 1; text-style: bold; color: $success; }
    #run-table { height: 40%; border: round $secondary; }
    #run-log { height: 1fr; border: round $primary; }
    """

    BINDINGS = [
        Binding("c", "convert", "Convert"),
        Binding("x", "remove", "Remove"),
        Binding("C", "clear", "Clear all"),
        Binding("h", "hidden", "Hidden files"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, root: Path | None = None):
        super().__init__()
        self.root = root or Path.home()
        self.selected: list[Path] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield SupportedTree(str(self.root), id="tree-pane")
            with Vertical(id="side-pane"):
                yield Label("Selection (0)", id="sel-title")
                yield DataTable(id="sel-table", cursor_type="row")
                yield Static(
                    "Enter/Space add file in tree · [b]c[/b] convert · [b]x[/b] remove · "
                    "[b]C[/b] clear · [b]h[/b] hidden · [b]q[/b] quit",
                    id="hints")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sel-table", DataTable)
        table.add_columns("File", "Type", "Size")

    # ── selection handling ──────────────────────────────────────────────
    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        p = Path(event.path)
        if p in self.selected:
            return
        self.selected.append(p)
        table = self.query_one("#sel-table", DataTable)
        try:
            size = _human_size(p.stat().st_size)
        except OSError:
            size = "?"
        table.add_row(p.name, get_file_category(p), size, key=str(p))
        self._update_title()

    def _update_title(self) -> None:
        self.query_one("#sel-title", Label).update(f"Selection ({len(self.selected)})")

    def action_remove(self) -> None:
        table = self.query_one("#sel-table", DataTable)
        if not self.selected or table.cursor_row is None:
            return
        try:
            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
        except Exception:
            return
        table.remove_row(row_key)
        self.selected = [p for p in self.selected if str(p) != row_key.value]
        self._update_title()

    def action_clear(self) -> None:
        self.query_one("#sel-table", DataTable).clear()
        self.selected = []
        self._update_title()

    def action_hidden(self) -> None:
        tree = self.query_one(SupportedTree)
        tree.show_hidden = not tree.show_hidden
        tree.reload()

    # ── convert flow ────────────────────────────────────────────────────
    def action_convert(self) -> None:
        if not self.selected:
            self.notify("No files selected — pick some in the tree first.", severity="warning")
            return
        cats = {_get_ext_category(p.suffix.lower()) for p in self.selected}
        cat = cats.pop() if len(cats) == 1 else "mixed"

        def _chosen(action):
            if action is None:
                return
            label, runner = action
            self.push_screen(RunScreen(list(self.selected), label, runner))

        self.push_screen(ActionPicker(cat, len(self.selected)), _chosen)


def run_tui() -> None:
    TranscripeTUI().run()


if __name__ == "__main__":
    run_tui()
