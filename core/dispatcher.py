from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import box
import questionary
from questionary import Style
from engines import audio_video, documents, images, data

# ── Theme ──────────────────────────────────────────────────────────────────
THEME = Style([
    ("qmark",       "fg:#673ab7 bold"),
    ("question",    "fg:#ffffff bold"),
    ("answer",      "fg:#00e676 bold"),
    ("pointer",     "fg:#673ab7 bold"),
    ("highlighted", "fg:#673ab7 bold"),
    ("selected",    "fg:#00e676"),
])

# ── Supported Extensions ──────────────────────────────────────────────────
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".mpeg", ".mpg", ".m4v", ".ts", ".3gp"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus", ".amr"}
MEDIA_AUDIO_TARGETS = {"mp3", "wav", "flac", "aac", "ogg", "m4a", "opus", "wma"}
MEDIA_VIDEO_TARGETS = {"mp4", "mkv", "avi", "mov", "webm", "flv", "wmv"}
DOC_EXTS   = {".pptx", ".ppt", ".docx", ".doc", ".epub", ".odt", ".rtf", ".txt", ".md",
              ".html", ".htm", ".tex", ".rst"}
DATA_EXTS  = {".csv", ".json", ".yaml", ".yml", ".xml", ".xls", ".xlsx", ".ods"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tiff", ".tif", ".gif", ".ico", ".svg", ".avif"}
PDF_EXTS   = {".pdf"}

ALL_SUPPORTED_EXTS = VIDEO_EXTS | AUDIO_EXTS | DOC_EXTS | DATA_EXTS | IMAGE_EXTS | PDF_EXTS

# ── Category helpers ──────────────────────────────────────────────────────

def get_file_category(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext in VIDEO_EXTS:  return "🎬 Video"
    if ext in AUDIO_EXTS:  return "🎵 Audio"
    if ext in DOC_EXTS:    return "📄 Document"
    if ext in IMAGE_EXTS:  return "🖼️  Image"
    if ext in PDF_EXTS:    return "📕 PDF"
    return "❓ Unknown"

def _get_ext_category(ext: str) -> str:
    ext = ext.lower()
    if ext in VIDEO_EXTS:  return "video"
    if ext in AUDIO_EXTS:  return "audio"
    if ext in DOC_EXTS:    return "document"
    if ext in DATA_EXTS:   return "data"
    if ext in IMAGE_EXTS:  return "image"
    if ext in PDF_EXTS:    return "pdf"
    return "unknown"

# ── Single-file conversion ────────────────────────────────────────────────

def _process_single_file(input_path: Path, target_format: str | None, console: Console):
    """Route a single file to the appropriate engine."""
    ext = input_path.suffix.lower()

    # INTERACTIVE: ask user to pick output format
    if target_format is None:
        if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
            is_video = ext in VIDEO_EXTS
            choices = [
                "📝  Transcription (.txt)",
                "🎬  Subtitles (.srt)",
            ]
            if is_video:
                choices += [
                    "🎵  Extract Audio (.mp3)",
                    "🎵  Extract Audio (.wav)",
                    "🎵  Extract Audio (.flac)",
                    "🎞️   Convert to GIF",
                    "📦  Compress Video (reduce file size)",
                    "✂️   Trim / Clip Video",
                    "🖼️   Extract Frames as Images",
                    "🔄  Convert to another format",
                ]
            else:
                choices += [
                    "🔄  Convert to MP3",
                    "🔄  Convert to WAV",
                    "🔄  Convert to FLAC",
                    "🔄  Convert to OGG",
                    "🔄  Convert to another format",
                ]
            choice = questionary.select(
                f"  {input_path.name} → What would you like to do?",
                choices=choices,
                style=THEME,
            ).ask()

            if "Transcription" in choice:       target_format = "txt"
            elif "Subtitles" in choice:         target_format = "srt"
            elif ".mp3" in choice or "MP3" in choice: target_format = "mp3"
            elif ".wav" in choice or "WAV" in choice: target_format = "wav"
            elif ".flac" in choice or "FLAC" in choice: target_format = "flac"
            elif "OGG" in choice:               target_format = "ogg"
            elif "GIF" in choice:               target_format = "__gif"
            elif "Compress" in choice:          target_format = "__compress"
            elif "Trim" in choice:              target_format = "__trim"
            elif "Frames" in choice:            target_format = "__frames"
            elif "another" in choice.lower():
                target_format = questionary.text(
                    "Enter target format (mp3, wav, flac, ogg, mp4, mkv, webm…):",
                    style=THEME,
                ).ask()

        elif ext in PDF_EXTS:
            choice = questionary.select(
                f"  {input_path.name} → What would you like to do?",
                choices=[
                    "📝  Extract Text from PDF",
                    "🖼️   Convert Pages to Images (PNG)",
                    "✂️   Split / Extract Pages",
                    "📝  Markdown (.md)",
                    "🌐  HTML Page (.html)",
                    "📄  Word Document (.docx)",
                ],
                style=THEME,
            ).ask()
            if "Extract Text" in choice:   target_format = "__pdf_text"
            elif "Images" in choice:       target_format = "__pdf_images"
            elif "Split" in choice:        target_format = "__pdf_split"
            elif "Markdown" in choice:     target_format = "md"
            elif "HTML" in choice:         target_format = "html"
            elif "Word" in choice:         target_format = "docx"

        elif ext in DOC_EXTS:
            choice = questionary.select(
                f"  {input_path.name} → What would you like to generate?",
                choices=[
                    "📕  PDF Document (.pdf)",
                    "📝  Markdown (.md)",
                    "🌐  HTML Page (.html)",
                    "📄  Word Document (.docx)",
                    "📃  Plain Text (.txt)",
                ],
                style=THEME,
            ).ask()
            if "PDF" in choice:        target_format = "pdf"
            elif "Markdown" in choice: target_format = "md"
            elif "HTML" in choice:     target_format = "html"
            elif "Word" in choice:     target_format = "docx"
            else:                      target_format = "txt"

        elif ext in DATA_EXTS:
            data_choices = []
            if ext == ".csv":
                data_choices = ["📊  JSON (.json)", "📊  Excel (.xlsx)"]
            elif ext == ".json":
                data_choices = ["📊  CSV (.csv)", "📊  YAML (.yaml)", "✨  Prettify JSON", "📦  Minify JSON"]
            elif ext in (".yaml", ".yml"):
                data_choices = ["📊  JSON (.json)"]
            elif ext in (".xls", ".xlsx", ".ods"):
                data_choices = ["📊  CSV (.csv)", "📊  JSON (.json)"]
            elif ext == ".xml":
                data_choices = ["📊  JSON (.json)"]

            choice = questionary.select(
                f"  {input_path.name} → What would you like to generate?",
                choices=data_choices,
                style=THEME,
            ).ask()

            if "CSV" in choice:       target_format = "csv"
            elif "JSON" in choice and "Prettify" not in choice and "Minify" not in choice:
                target_format = "json"
            elif "Excel" in choice:   target_format = "xlsx"
            elif "YAML" in choice:    target_format = "yaml"
            elif "Prettify" in choice: target_format = "__json_pretty"
            elif "Minify" in choice:  target_format = "__json_minify"

        elif ext in IMAGE_EXTS:
            choice = questionary.select(
                f"  {input_path.name} → What would you like to do?",
                choices=[
                    "📝  Extract Text (OCR → .txt)",
                    "🖼️   Convert to PNG",
                    "🖼️   Convert to WebP",
                    "🖼️   Convert to JPEG",
                    "📐  Resize Image",
                    "📦  Compress Image (reduce file size)",
                    "📕  Convert to PDF",
                ],
                style=THEME,
            ).ask()
            if "OCR" in choice:       target_format = "txt"
            elif "PNG" in choice:     target_format = "png"
            elif "WebP" in choice:    target_format = "webp"
            elif "JPEG" in choice:    target_format = "jpg"
            elif "Resize" in choice:  target_format = "__resize"
            elif "Compress" in choice: target_format = "__compress_img"
            elif "PDF" in choice:     target_format = "__img_pdf"

        else:
            raise ValueError(f"No interactive options for '{ext}'. Use --to flag.")

    # ── Special interactive actions (not a simple format string) ──
    if target_format.startswith("__"):
        if target_format == "__gif":
            fps = int(questionary.text("GIF frames per second?", default="10", style=THEME).ask())
            width = int(questionary.text("GIF width in pixels?", default="480", style=THEME).ask())
            audio_video.video_to_gif(input_path, fps, width, console)
        elif target_format == "__compress":
            q = questionary.select("Compression quality?", choices=["high (minimal loss)", "medium (balanced)", "low (smallest file)"], style=THEME).ask()
            audio_video.compress_video(input_path, q.split()[0], console)
        elif target_format == "__trim":
            start = questionary.text("Start time (e.g., 00:00:30 or 30):", default="00:00:00", style=THEME).ask()
            end = questionary.text("End time (e.g., 00:01:45 or leave blank for end):", default="", style=THEME).ask()
            audio_video.trim_video(input_path, start, end, console)
        elif target_format == "__frames":
            fps = int(questionary.text("Extract how many frames per second?", default="1", style=THEME).ask())
            audio_video.extract_frames(input_path, fps, console)
        elif target_format == "__pdf_text":
            documents.pdf_to_text(input_path, console)
        elif target_format == "__pdf_images":
            documents.pdf_to_images(input_path, console)
        elif target_format == "__pdf_split":
            page_range = questionary.text("Enter page range (e.g., 1-5 or 3,7,10-12):", style=THEME).ask()
            documents.split_pdf(input_path, page_range, console)
        elif target_format == "__resize":
            w = questionary.text("Target width in pixels (leave blank to auto):", default="", style=THEME).ask()
            h = questionary.text("Target height in pixels (leave blank to auto):", default="", style=THEME).ask()
            images.resize_image(input_path, int(w) if w else None, int(h) if h else None, console)
        elif target_format == "__compress_img":
            q = int(questionary.text("Quality (1-100, lower = smaller):", default="60", style=THEME).ask())
            images.compress_image(input_path, q, console)
        elif target_format == "__img_pdf":
            images.image_to_pdf(input_path, console)
        elif target_format == "__json_pretty":
            data.json_prettify(input_path, console)
        elif target_format == "__json_minify":
            data.json_minify(input_path, console)
        return

    # ── Standard format routing ──
    target_format = target_format.lower().strip(".")

    if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
        if target_format in ("txt", "srt"):
            audio_video.transcribe(input_path, target_format, console)
        elif target_format in MEDIA_AUDIO_TARGETS or target_format in MEDIA_VIDEO_TARGETS:
            audio_video.convert_media(input_path, target_format, console)
        else:
            raise ValueError(f"Cannot convert video/audio to .{target_format}")

    elif ext in PDF_EXTS:
        if target_format in ("md", "html", "docx", "txt"):
            documents.convert_with_pandoc(input_path, target_format, console)
        else:
            raise ValueError(f"Cannot convert PDF to .{target_format}")

    elif ext in DOC_EXTS:
        if target_format == "pdf":
            documents.convert_document_to_pdf_engine(input_path, console)
        else:
            documents.convert_with_pandoc(input_path, target_format, console)

    elif ext in DATA_EXTS:
        if ext == ".csv" and target_format == "json":
            data.csv_to_json(input_path, console)
        elif ext == ".csv" and target_format == "xlsx":
            data.csv_to_excel(input_path, console)
        elif ext == ".json" and target_format == "csv":
            data.json_to_csv(input_path, console)
        elif ext == ".json" and target_format == "yaml":
            data.json_to_yaml(input_path, console)
        elif ext in (".yaml", ".yml") and target_format == "json":
            data.yaml_to_json(input_path, console)
        elif ext in (".xls", ".xlsx", ".ods") and target_format == "csv":
            data.excel_to_csv(input_path, console)
        elif ext in (".xls", ".xlsx", ".ods") and target_format == "json":
            data.excel_to_csv(input_path, console)  # CSV first, then to JSON
        else:
            raise ValueError(f"Cannot convert {ext} to .{target_format}")

    elif ext in IMAGE_EXTS:
        images.convert_image(input_path, target_format, console)

    else:
        raise ValueError(f"Unsupported format: {ext}")


# ── Multi-file conversion ────────────────────────────────────────────────

def dispatch_conversion(files: list[Path], target_format: str | None, console: Console):
    """Convert one or many files. Asks for format interactively if needed."""
    if len(files) == 1:
        _process_single_file(files[0], target_format, console)
        return

    # Multiple files: show what we have, ask for a format strategy
    console.print(f"[bold cyan]Processing {len(files)} files:[/bold cyan]")

    # Group by category
    categories = {}
    for f in files:
        cat = _get_ext_category(f.suffix.lower())
        categories.setdefault(cat, []).append(f)

    # If all same category, ask once
    if len(categories) == 1:
        cat = list(categories.keys())[0]
        if target_format is None:
            target_format = _ask_format_for_category(cat)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[bold green]{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Converting…", total=len(files))
            for f in files:
                try:
                    progress.update(task, description=f"Converting {f.name}…")
                    _process_single_file(f, target_format, console)
                except Exception as e:
                    console.print(f"  [dim red]⚠ Skipped {f.name}: {e}[/dim red]")
                progress.advance(task)

    else:
        # Mixed types: ask per-file or use a uniform format
        strategy = questionary.select(
            "You selected files of different types. How should I convert them?",
            choices=[
                "🎯  Ask me for each file individually",
                "📄  Convert everything to Text (.txt)",
                "📕  Convert everything to PDF (.pdf)",
            ],
            style=THEME,
        ).ask()

        fmt = None
        if "Text" in strategy: fmt = "txt"
        elif "PDF" in strategy: fmt = "pdf"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[bold green]{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Converting…", total=len(files))
            for f in files:
                try:
                    progress.update(task, description=f"Converting {f.name}…")
                    _process_single_file(f, fmt, console)
                except Exception as e:
                    console.print(f"  [dim red]⚠ Skipped {f.name}: {e}[/dim red]")
                progress.advance(task)

    console.print(f"\n[bold green]✓ Batch conversion complete![/bold green]")


def _ask_format_for_category(cat: str) -> str:
    """Ask the user for an output format based on file category."""
    if cat in ("video", "audio"):
        c = questionary.select(
            "Output format for all video/audio files?",
            choices=["📝 Transcription (.txt)", "🎬 Subtitles (.srt)"],
            style=THEME,
        ).ask()
        return "txt" if "Transcription" in c else "srt"

    elif cat in ("document", "pdf"):
        c = questionary.select(
            "Output format for all documents?",
            choices=[
                "📕 PDF (.pdf)", "📝 Markdown (.md)", "🌐 HTML (.html)",
                "📄 Word (.docx)", "📃 Plain Text (.txt)",
            ],
            style=THEME,
        ).ask()
        if "PDF" in c:        return "pdf"
        elif "Markdown" in c: return "md"
        elif "HTML" in c:     return "html"
        elif "Word" in c:     return "docx"
        else:                 return "txt"

    elif cat == "image":
        c = questionary.select(
            "Output format for all images?",
            choices=[
                "📝 Extract Text – OCR (.txt)", "🖼️  PNG", "🖼️  WebP", "🖼️  JPEG",
            ],
            style=THEME,
        ).ask()
        if "OCR" in c:   return "txt"
        elif "PNG" in c: return "png"
        elif "WebP" in c: return "webp"
        else:            return "jpg"

    return questionary.text("Enter target extension:", style=THEME).ask() or "txt"


# ── Merge Engine ──────────────────────────────────────────────────────────

def dispatch_merge(files: list[Path], console: Console):
    """Interactive merge wizard for combining multiple files."""
    if len(files) < 2:
        raise ValueError("You need at least 2 files to merge.")

    # Show files in order
    table = Table(title="Files to Merge (in this order)", box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan")
    table.add_column("Type", style="yellow")
    for i, f in enumerate(files, 1):
        table.add_row(str(i), f.name, get_file_category(f))
    console.print(table)

    # Reorder?
    reorder = questionary.confirm("Would you like to reorder these files?", default=False, style=THEME).ask()
    if reorder:
        console.print("[dim]Enter the new order as numbers separated by spaces (e.g., 3 1 2):[/dim]")
        order_str = questionary.text("New order:", style=THEME).ask()
        try:
            indices = [int(x) - 1 for x in order_str.split()]
            files = [files[i] for i in indices]
            console.print("[green]✓ Files reordered.[/green]")
        except Exception:
            console.print("[yellow]Invalid order. Keeping original sequence.[/yellow]")

    # Detect what kind of merge is possible
    exts = {f.suffix.lower() for f in files}
    all_text   = all(_get_ext_category(e) in ("document",) for e in exts) or all(e in (".txt", ".md") for e in exts)
    all_images = all(e in IMAGE_EXTS for e in exts)
    all_pdf    = all(e in (".pdf",) for e in exts)
    all_audio  = all(e in AUDIO_EXTS or e in VIDEO_EXTS for e in exts)

    # Choose merge type
    merge_choices = []
    if all_text or all_pdf:
        merge_choices.append("📄  Merge into a single Text file (.txt)")
        merge_choices.append("📝  Merge into a single Markdown file (.md)")
    if all_pdf:
        merge_choices.append("📕  Merge PDFs into one PDF")
    if all_images:
        merge_choices.append("📕  Combine images into a single PDF")
        merge_choices.append("🖼️   Stitch images vertically into one image")
        merge_choices.append("🖼️   Create a side-by-side collage")
    if all_audio:
        merge_choices.append("🎵  Concatenate audio/video into one file")
    # Always available
    merge_choices.append("📃  Merge all content into a single Text file")

    merge_type = questionary.select(
        "How would you like to merge these files?",
        choices=merge_choices,
        style=THEME,
    ).ask()

    # Output location
    default_out = files[0].parent / f"merged_output{_ext_for_merge(merge_type)}"
    out_path_str = questionary.text(
        f"Where should I save the merged file?",
        default=str(default_out),
        style=THEME,
    ).ask()
    out_path = Path(out_path_str).expanduser().resolve()

    # Execute merge
    with console.status(f"[bold cyan]Merging {len(files)} files…[/bold cyan]"):
        if "PDF" in merge_type and "images" in merge_type.lower():
            _merge_images_to_pdf(files, out_path, console)
        elif "Stitch" in merge_type or "vertically" in merge_type.lower():
            _merge_images_vertical(files, out_path, console)
        elif "collage" in merge_type.lower():
            _merge_images_collage(files, out_path, console)
        elif "PDFs into one" in merge_type:
            _merge_pdfs(files, out_path, console)
        elif "Concatenate audio" in merge_type:
            _merge_audio(files, out_path, console)
        elif "Text" in merge_type or "Markdown" in merge_type:
            _merge_text_files(files, out_path, merge_type, console)
        else:
            _merge_text_files(files, out_path, merge_type, console)

    console.print(f"\n[bold green]✓ Merged! Saved to:[/bold green] [underline]{out_path}[/underline]")


def _ext_for_merge(merge_type: str) -> str:
    if "PDF" in merge_type:  return ".pdf"
    if "Markdown" in merge_type: return ".md"
    if "image" in merge_type.lower() and "Stitch" in merge_type: return ".png"
    if "collage" in merge_type.lower(): return ".png"
    if "audio" in merge_type.lower(): return ".mp4"
    return ".txt"


def _merge_text_files(files: list[Path], out_path: Path, merge_type: str, console: Console):
    """Merge text/document files into a single text or markdown file."""
    # Ask for separator
    sep_choice = questionary.select(
        "How should files be separated in the merged document?",
        choices=[
            "📏  Horizontal line (---)",
            "📄  Filename as header",
            "🔢  Numbered sections",
            "⬜  Blank line only",
            "🚫  No separator (continuous)",
        ],
        style=THEME,
    ).ask()

    with open(out_path, "w", encoding="utf-8") as out:
        for i, f in enumerate(files):
            # Write separator
            if i > 0:
                if "Horizontal" in sep_choice:
                    out.write("\n\n---\n\n")
                elif "Filename" in sep_choice:
                    out.write(f"\n\n## {f.name}\n\n")
                elif "Numbered" in sep_choice:
                    out.write(f"\n\n## Section {i + 1}: {f.stem}\n\n")
                elif "Blank" in sep_choice:
                    out.write("\n\n")
                # No separator: nothing

            # Read content
            try:
                content = f.read_text(encoding="utf-8")
                out.write(content)
            except UnicodeDecodeError:
                out.write(f"[Binary file: {f.name}]\n")
            except Exception as e:
                out.write(f"[Error reading {f.name}: {e}]\n")

            console.print(f"  [dim]+ {f.name}[/dim]")


def _merge_images_to_pdf(files: list[Path], out_path: Path, console: Console):
    """Combine images into a single PDF document."""
    from PIL import Image
    images_list = []
    for f in files:
        img = Image.open(f).convert("RGB")
        images_list.append(img)
        console.print(f"  [dim]+ {f.name} ({img.width}x{img.height})[/dim]")
    if images_list:
        images_list[0].save(out_path, save_all=True, append_images=images_list[1:])


def _merge_images_vertical(files: list[Path], out_path: Path, console: Console):
    """Stitch images vertically into one tall image."""
    from PIL import Image
    imgs = [Image.open(f) for f in files]
    max_w = max(im.width for im in imgs)
    total_h = sum(im.height for im in imgs)
    result = Image.new("RGB", (max_w, total_h), (255, 255, 255))
    y = 0
    for im, f in zip(imgs, files):
        result.paste(im, (0, y))
        y += im.height
        console.print(f"  [dim]+ {f.name}[/dim]")
    result.save(out_path)


def _merge_images_collage(files: list[Path], out_path: Path, console: Console):
    """Create a side-by-side collage from images."""
    from PIL import Image
    imgs = [Image.open(f) for f in files]
    max_h = max(im.height for im in imgs)
    total_w = sum(im.width for im in imgs)
    result = Image.new("RGB", (total_w, max_h), (255, 255, 255))
    x = 0
    for im, f in zip(imgs, files):
        result.paste(im, (x, 0))
        x += im.width
        console.print(f"  [dim]+ {f.name}[/dim]")
    result.save(out_path)


def _merge_pdfs(files: list[Path], out_path: Path, console: Console):
    """Merge multiple PDF files into one."""
    try:
        from pypdf import PdfMerger
    except ImportError:
        try:
            from PyPDF2 import PdfMerger
        except ImportError:
            console.print("[red]PDF merging requires 'pypdf'. Installing...[/red]")
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
            from pypdf import PdfMerger

    merger = PdfMerger()
    for f in files:
        merger.append(str(f))
        console.print(f"  [dim]+ {f.name}[/dim]")
    merger.write(str(out_path))
    merger.close()


def _merge_audio(files: list[Path], out_path: Path, console: Console):
    """Concatenate audio/video files using FFmpeg."""
    import shutil, tempfile
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

    # Create a concat list file
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        for f in files:
            tmp.write(f"file '{f}'\n")
            console.print(f"  [dim]+ {f.name}[/dim]")
        list_path = tmp.name

    import subprocess
    subprocess.run(
        [ffmpeg, "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", str(out_path), "-y"],
        capture_output=True,
    )
    Path(list_path).unlink()
