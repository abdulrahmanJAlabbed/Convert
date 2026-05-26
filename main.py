"""Convert PPTX files to PDF from the command line using LibreOffice."""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("pptx-to-pdf")


def find_soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def iter_pptx_files(target: Path):
    if target.is_file():
        yield target
        return

    if target.is_dir():
        yield from sorted(target.glob("*.pptx"))
        return

    raise FileNotFoundError(f"Input not found: {target}")


def convert_pptx_to_pdf(soffice: str, pptx_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pptx_pdf_") as profile_dir:
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
                str(pptx_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"LibreOffice failed for {pptx_path.name}: {stderr}")

    generated = output_path.parent / f"{pptx_path.stem}.pdf"
    if not generated.exists():
        raise RuntimeError(f"LibreOffice did not create {generated}")

    if generated != output_path:
        if output_path.exists():
            output_path.unlink()
        generated.replace(output_path)

    return output_path


def resolve_output_path(source: Path, output_arg: str | None) -> Path:
    if output_arg is None:
        return source.with_suffix(".pdf")

    output = Path(output_arg)
    if output.exists() and output.is_dir():
        return output / f"{source.stem}.pdf"

    if output.suffix.lower() == ".pdf":
        return output

    if len(output.parts) == 1 and not output.suffix:
        return output / f"{source.stem}.pdf"

    return output / f"{source.stem}.pdf"


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert PPTX files to PDF using LibreOffice")
    parser.add_argument("input", nargs="+", help="Input .pptx file(s) or folder(s)")
    parser.add_argument("-o", "--output", help="Output PDF file or output folder")
    args = parser.parse_args()

    soffice = find_soffice()
    if not soffice:
        logger.error("LibreOffice CLI not found. Install soffice/libreoffice and try again.")
        return 1

    sources = [Path(item).expanduser().resolve() for item in args.input]
    pptx_files = []
    for source in sources:
        pptx_files.extend(iter_pptx_files(source))

    if not pptx_files:
        logger.error("No .pptx files found to convert.")
        return 1

    failures = 0
    for pptx_path in pptx_files:
        try:
            output_path = resolve_output_path(pptx_path, args.output)
            pdf_path = convert_pptx_to_pdf(soffice, pptx_path, output_path)
            logger.info("Created %s", pdf_path)
        except Exception as exc:
            failures += 1
            logger.error("%s", exc)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
