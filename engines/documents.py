import os
import sys
import shutil
import tempfile
import subprocess
import pypandoc
from pathlib import Path
from rich.console import Console

def find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def _libreoffice_to_pdf(doc_path: Path, output_path: Path, console: Console) -> None:
    """Convert a document to PDF using headless LibreOffice. Raises on failure."""
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice not found. Install soffice/libreoffice.")

    with console.status(f"[bold cyan]Converting {doc_path.name} → PDF (LibreOffice)…[/bold cyan]"):
        with tempfile.TemporaryDirectory(prefix="doc_pdf_") as profile_dir:
            result = subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation=file://{Path(profile_dir).as_posix()}",
                    "--headless", "--nologo", "--nolockcheck", "--nodefault",
                    "--convert-to", "pdf",
                    "--outdir", str(output_path.parent),
                    str(doc_path),
                ],
                capture_output=True, text=True, check=False,
            )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(f"LibreOffice failed: {stderr}")

        generated = output_path.parent / f"{doc_path.stem}.pdf"
        if not generated.exists():
            raise RuntimeError(f"LibreOffice did not create {generated.name}")
        if generated != output_path:
            if output_path.exists():
                output_path.unlink()
            generated.replace(output_path)


def _powerpoint_to_pdf(src: Path, out: Path) -> None:
    """Export PowerPoint → PDF via MS Office (Windows COM / macOS AppleScript)."""
    if sys.platform.startswith("win"):
        import comtypes.client  # type: ignore
        powerpoint = comtypes.client.CreateObject("PowerPoint.Application")
        deck = None
        try:
            deck = powerpoint.Presentations.Open(str(src), WithWindow=False)
            deck.SaveAs(str(out), 32)  # 32 = ppSaveAsPDF
        finally:
            if deck is not None:
                deck.Close()
            powerpoint.Quit()
    elif sys.platform == "darwin":
        script = (
            'tell application "Microsoft PowerPoint"\n'
            f'  open POSIX file "{src}"\n'
            '  set theDoc to active presentation\n'
            f'  save theDoc in POSIX file "{out}" as save as PDF\n'
            '  close theDoc saving no\n'
            'end tell'
        )
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
    else:
        raise RuntimeError("MS PowerPoint automation is only available on Windows/macOS")


def _msoffice_to_pdf(doc_path: Path, output_path: Path, console: Console) -> None:
    """Convert Word/PowerPoint → PDF using MS Office. Raises on failure."""
    ext = doc_path.suffix.lower()
    with console.status(f"[bold cyan]Converting {doc_path.name} → PDF (MS Office)…[/bold cyan]"):
        if ext in (".docx", ".doc"):
            from docx2pdf import convert as _docx_convert  # type: ignore
            _docx_convert(str(doc_path), str(output_path))
        elif ext in (".pptx", ".ppt"):
            _powerpoint_to_pdf(doc_path, output_path)
        else:
            raise RuntimeError(f"MS Office backend does not handle {ext}")
    if not output_path.exists():
        raise RuntimeError("MS Office produced no output")


def convert_document_to_pdf_engine(doc_path: Path, console: Console,
                                   output_path: Path | None = None, backend: str | None = None):
    """Convert a document to PDF, auto-picking the best available backend.

    Order: MS Office for .docx/.pptx when present (highest fidelity), else LibreOffice.
    Any MS Office failure self-heals to LibreOffice so output is always produced.
    Override with the TRANSCRIPE_DOC_BACKEND env var or the `backend` argument.
    """
    from core import capabilities

    output_path = output_path or doc_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chosen = backend or os.environ.get("TRANSCRIPE_DOC_BACKEND") \
        or capabilities.doc_pdf_backend(doc_path.suffix)
    if not chosen:
        raise RuntimeError("No document→PDF backend available. Install LibreOffice.")

    if chosen == "msoffice":
        try:
            _msoffice_to_pdf(doc_path, output_path, console)
            console.print(f"[bold green]✓ Created {output_path.name}[/bold green] [dim](MS Office)[/dim]")
            return
        except Exception as e:
            console.print(f"[yellow]MS Office backend unavailable ({e}); using LibreOffice.[/yellow]")

    _libreoffice_to_pdf(doc_path, output_path, console)
    console.print(f"[bold green]✓ Created {output_path.name}[/bold green] [dim](LibreOffice)[/dim]")

# Map friendly extensions to the format names pandoc actually expects.
_PANDOC_WRITER = {"txt": "plain", "text": "plain", "markdown": "gfm", "md": "gfm"}



def _pandoc_writer(target_format: str) -> str:
    return _PANDOC_WRITER.get(target_format, target_format)


def convert_with_pandoc(input_path: Path, target_format: str, console: Console, output_path: Path | None = None):
    out_path = output_path or input_path.with_suffix(f".{target_format}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    to_format = _pandoc_writer(target_format)
    extra_args = ["--standalone"] if target_format in ("html", "htm") else []

    with console.status(f"[bold cyan]Converting {input_path.name} to {target_format.upper()} using Pandoc...[/bold cyan]"):
        try:
            pypandoc.convert_file(str(input_path), to_format, outputfile=str(out_path), extra_args=extra_args)
        except OSError as e:
            raise RuntimeError(
                "Pandoc not found. Install pandoc or run: "
                "python -c \"import pypandoc; pypandoc.download_pandoc()\""
            ) from e

    if not out_path.exists():
        raise RuntimeError(f"Pandoc did not produce {out_path.name}")
    console.print(f"[bold green]✓ Converted! Saved to {out_path.name}[/bold green]")


def pdf_to_document(pdf_path: Path, target_format: str, console: Console, output_path: Path | None = None):
    """Convert a PDF to md/html/docx/txt by extracting its text first (pandoc can't read PDF)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
        from pypdf import PdfReader

    out_path = output_path or pdf_path.with_suffix(f".{target_format}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Extracting text from {pdf_path.name} → {target_format.upper()}…[/bold cyan]"):
        reader = PdfReader(str(pdf_path))
        parts = []
        for i, page in enumerate(reader.pages, 1):
            parts.append(f"## Page {i}\n\n{(page.extract_text() or '').strip()}")
        text = "\n\n".join(parts)

    if len(text.replace("#", "").split()) < 5:
        console.print(
            "[yellow]⚠ This PDF appears to be scanned/image-based — almost no selectable text was found. "
            "Try 'Convert Pages to Images' + OCR instead.[/yellow]"
        )

    to_format = _pandoc_writer(target_format)
    extra_args = ["--standalone"] if target_format in ("html", "htm") else []
    try:
        pypandoc.convert_text(text, to_format, format="markdown",
                              outputfile=str(out_path), extra_args=extra_args)
    except OSError as e:
        raise RuntimeError(
            "Pandoc not found. Install pandoc or run: "
            "python -c \"import pypandoc; pypandoc.download_pandoc()\""
        ) from e

    console.print(f"[bold green]✓ Converted! Saved to {out_path.name}[/bold green]")


def pdf_ocr(pdf_path: Path, console: Console, output_path: Path | None = None,
            langs: list[str] | None = None, dpi: int = 200):
    """OCR a scanned/image-based PDF: render each page to an image, then run OCR."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pdf2image"])
        from pdf2image import convert_from_path

    import tempfile
    from engines import ocr

    out_path = output_path or pdf_path.with_suffix(".txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    engine = ocr.available_engine(langs)
    lang_label = ", ".join(langs) if langs else "auto"

    with console.status(f"[bold cyan]Rendering {pdf_path.name} for OCR ({engine}, {lang_label})…[/bold cyan]"):
        pages = convert_from_path(str(pdf_path), dpi=dpi)

    parts = []
    with tempfile.TemporaryDirectory(prefix="pdf_ocr_") as tmp:
        for i, page in enumerate(pages, 1):
            img_path = Path(tmp) / f"page_{i:03d}.png"
            page.save(str(img_path), "PNG")
            text = ocr.ocr_image(img_path, langs)
            parts.append(f"--- Page {i} ---\n{text}")
            console.print(f"  [dim]Page {i}/{len(pages)} — {len(text)} chars[/dim]")

    full_text = "\n\n".join(parts)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    console.print(f"[bold green]✓ OCR'd {len(pages)} pages → {out_path.name}[/bold green] [dim]({len(full_text)} chars)[/dim]")


def pdf_to_images(pdf_path: Path, console: Console, output_path: Path | None = None):
    """Convert each page of a PDF into a PNG image."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        console.print("[red]Missing dependency. Installing pdf2image...[/red]")
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pdf2image"])
        from pdf2image import convert_from_path

    out_dir = output_path or (pdf_path.parent / f"{pdf_path.stem}_pages")
    out_dir.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting {pdf_path.name} pages to PNG images…[/bold cyan]"):
        images = convert_from_path(str(pdf_path), dpi=200)

    for i, img in enumerate(images, 1):
        out_file = out_dir / f"page_{i:03d}.png"
        img.save(str(out_file), "PNG")
        console.print(f"  [dim]+ page_{i:03d}.png ({img.width}x{img.height})[/dim]")

    console.print(f"[bold green]✓ Extracted {len(images)} pages to {out_dir.name}/[/bold green]")


def pdf_to_text(pdf_path: Path, console: Console, output_path: Path | None = None):
    """Extract raw text from a PDF using pypdf (no OCR needed for text-based PDFs)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        console.print("[red]Missing dependency. Installing pypdf...[/red]")
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
        from pypdf import PdfReader

    out_path = output_path or pdf_path.with_suffix(".txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Extracting text from {pdf_path.name}…[/bold cyan]"):
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for i, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            text_parts.append(f"--- Page {i} ---\n{page_text}")
            console.print(f"  [dim]Page {i}/{len(reader.pages)} — {len(page_text)} chars[/dim]")

        full_text = "\n\n".join(text_parts)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    if len(full_text.replace("-", "").split()) < len(reader.pages) + 3:
        console.print(
            "[yellow]⚠ Very little text extracted — this PDF is likely scanned/image-based. "
            "Re-run and choose '🔎 OCR — read scanned/image PDF' to read it with AI.[/yellow]"
        )
    console.print(f"[bold green]✓ Extracted text from {len(reader.pages)} pages → {out_path.name}[/bold green]")


def split_pdf(pdf_path: Path, page_range: str, console: Console, output_path: Path | None = None):
    """Extract specific pages from a PDF. page_range like '1-5' or '3,7,10-12'."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
        from pypdf import PdfReader, PdfWriter

    # Parse page range
    pages = set()
    for part in page_range.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(part))

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)

    # Validate
    invalid = [p for p in pages if p < 1 or p > total]
    if invalid:
        console.print(f"[red]Invalid pages: {invalid}. PDF has {total} pages.[/red]")
        return

    writer = PdfWriter()
    for p in sorted(pages):
        writer.add_page(reader.pages[p - 1])  # 0-indexed
        console.print(f"  [dim]+ Page {p}[/dim]")

    out_path = output_path or (
        pdf_path.parent / f"{pdf_path.stem}_pages_{page_range.replace(',', '_').replace('-', 'to')}.pdf"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        writer.write(f)

    console.print(f"[bold green]✓ Saved {len(pages)} pages → {out_path.name}[/bold green]")
