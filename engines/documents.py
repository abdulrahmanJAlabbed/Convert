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
