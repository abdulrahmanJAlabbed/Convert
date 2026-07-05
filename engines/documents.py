import shutil
import tempfile
import subprocess
import pypandoc
from pathlib import Path
from rich.console import Console

def find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")

def convert_document_to_pdf_engine(doc_path: Path, console: Console):
    soffice = find_soffice()
    if not soffice:
        console.print("[bold red]LibreOffice CLI not found. Install soffice/libreoffice and try again.[/bold red]")
        return
        
    output_path = doc_path.with_suffix(".pdf")
    
    with console.status(f"[bold cyan]Converting {doc_path.name} to PDF using LibreOffice...[/bold cyan]"):
        with tempfile.TemporaryDirectory(prefix="doc_pdf_") as profile_dir:
            result = subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation=file://{Path(profile_dir).as_posix()}",
                    "--headless",
                    "--nologo",
                    "--nolockcheck",
                    "--nodefault",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_path.parent),
                    str(doc_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
            console.print(f"[bold red]LibreOffice failed for {doc_path.name}:[/bold red] {stderr}")
            return
            
        generated = output_path.parent / f"{doc_path.stem}.pdf"
        if not generated.exists():
            console.print(f"[bold red]LibreOffice did not create {generated}[/bold red]")
            return

    console.print(f"[bold green]✓ Successfully created {output_path.name}[/bold green]")

def convert_with_pandoc(input_path: Path, target_format: str, console: Console):
    out_path = input_path.with_suffix(f".{target_format}")
    with console.status(f"[bold cyan]Converting {input_path.name} to {target_format.upper()} using Pandoc...[/bold cyan]"):
        try:
            # pypandoc automatically downloads pandoc if needed if we use download_pandoc(), 
            # but usually we just try to convert.
            pypandoc.convert_file(str(input_path), target_format, outputfile=str(out_path))
            console.print(f"[bold green]✓ Converted! Saved to {out_path.name}[/bold green]")
        except OSError:
            console.print("[bold red]Pandoc not found![/bold red] Please install pandoc on your system, or run: [yellow]python -c \"import pypandoc; pypandoc.download_pandoc()\"[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Conversion failed:[/bold red] {e}")


def pdf_to_images(pdf_path: Path, console: Console):
    """Convert each page of a PDF into a PNG image."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        console.print("[red]Missing dependency. Installing pdf2image...[/red]")
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pdf2image"])
        from pdf2image import convert_from_path

    out_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
    out_dir.mkdir(exist_ok=True)

    with console.status(f"[bold cyan]Converting {pdf_path.name} pages to PNG images…[/bold cyan]"):
        images = convert_from_path(str(pdf_path), dpi=200)

    for i, img in enumerate(images, 1):
        out_file = out_dir / f"page_{i:03d}.png"
        img.save(str(out_file), "PNG")
        console.print(f"  [dim]+ page_{i:03d}.png ({img.width}x{img.height})[/dim]")

    console.print(f"[bold green]✓ Extracted {len(images)} pages to {out_dir.name}/[/bold green]")


def pdf_to_text(pdf_path: Path, console: Console):
    """Extract raw text from a PDF using pypdf (no OCR needed for text-based PDFs)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        console.print("[red]Missing dependency. Installing pypdf...[/red]")
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"])
        from pypdf import PdfReader

    out_path = pdf_path.with_suffix(".txt")

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

    console.print(f"[bold green]✓ Extracted text from {len(reader.pages)} pages → {out_path.name}[/bold green]")


def split_pdf(pdf_path: Path, page_range: str, console: Console):
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

    out_path = pdf_path.parent / f"{pdf_path.stem}_pages_{page_range.replace(',', '_').replace('-', 'to')}.pdf"
    with open(out_path, "wb") as f:
        writer.write(f)

    console.print(f"[bold green]✓ Saved {len(pages)} pages → {out_path.name}[/bold green]")
