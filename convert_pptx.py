"""
PPTX to PDF Converter
======================
Converts .pptx files to .pdf using the best available method:
  1. PowerPoint COM (if installed) — most accurate
  2. LibreOffice CLI (if installed) — very accurate
  3. python-pptx + pdf rendering — fallback

Usage:
  python convert_pptx.py input.pptx              -> input.pdf
  python convert_pptx.py input.pptx output.pdf   -> output.pdf
  python convert_pptx.py folder/                  -> converts all .pptx in folder
"""

import sys, os, subprocess, shutil
from pathlib import Path


def find_libreoffice():
    """Find LibreOffice installation."""
    candidates = [
        shutil.which("soffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\LibreOffice\program\soffice.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def find_powerpoint():
    """Check if PowerPoint is available via COM."""
    try:
        import comtypes.client
        pp = comtypes.client.CreateObject("PowerPoint.Application")
        pp.Quit()
        return True
    except:
        return False


def convert_with_powerpoint(pptx_path, pdf_path):
    """Convert using PowerPoint COM automation (most accurate)."""
    import comtypes.client

    pptx_abs = str(Path(pptx_path).resolve())
    pdf_abs  = str(Path(pdf_path).resolve())

    pp = comtypes.client.CreateObject("PowerPoint.Application")
    pp.Visible = True
    try:
        deck = pp.Presentations.Open(pptx_abs, WithWindow=False)
        deck.SaveAs(pdf_abs, 32)  # 32 = ppSaveAsPDF
        deck.Close()
    finally:
        pp.Quit()
    print(f"  [PowerPoint] {pdf_path}")


def convert_with_libreoffice(pptx_path, pdf_path, soffice):
    """Convert using LibreOffice headless (very accurate)."""
    out_dir = str(Path(pdf_path).parent.resolve())
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, str(pptx_path)],
        capture_output=True, text=True, timeout=120
    )
    # LibreOffice names output after input file
    lo_output = Path(out_dir) / (Path(pptx_path).stem + ".pdf")
    target = Path(pdf_path)
    if lo_output.exists() and lo_output != target:
        lo_output.rename(target)
    if target.exists():
        print(f"  [LibreOffice] {pdf_path}")
    else:
        print(f"  [LibreOffice] FAILED: {result.stderr}")
        sys.exit(1)


def convert_with_python(pptx_path, pdf_path):
    """Fallback: extract slides as images and compile to PDF."""
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt, Emu
        from PIL import Image
        from reportlab.lib.pagesizes import inch
        from reportlab.pdfgen import canvas
    except ImportError:
        print("  ERROR: Install required packages: pip install python-pptx Pillow reportlab")
        sys.exit(1)

    prs = Presentation(pptx_path)
    slide_width  = prs.slide_width
    slide_height = prs.slide_height

    # This method is limited - it can extract text/shapes but not render perfectly
    # We'll create a simple text-based PDF as fallback
    w_inches = slide_width / 914400  # EMU to inches
    h_inches = slide_height / 914400

    c = canvas.Canvas(str(pdf_path), pagesize=(w_inches*inch, h_inches*inch))

    for slide_num, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        texts.append(text)

        y = h_inches * inch - 72  # Start near top
        c.setFont("Helvetica", 14)

        # Slide number header
        c.setFont("Helvetica-Bold", 10)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(36, h_inches * inch - 30, f"Slide {slide_num}")
        c.setFillColorRGB(0, 0, 0)

        c.setFont("Helvetica", 12)
        for text in texts:
            if y < 72:
                break
            # Wrap long lines
            words = text.split()
            line = ""
            for word in words:
                if c.stringWidth(line + " " + word, "Helvetica", 12) < (w_inches * inch - 72):
                    line = (line + " " + word).strip()
                else:
                    c.drawString(36, y, line)
                    y -= 16
                    line = word
            if line:
                c.drawString(36, y, line)
                y -= 20

        c.showPage()

    c.save()
    print(f"  [Python/text-only] {pdf_path}")
    print(f"  NOTE: Text-only conversion. For full fidelity, install LibreOffice.")


def convert(pptx_path, pdf_path=None):
    pptx_path = Path(pptx_path)
    if not pptx_path.exists():
        print(f"  File not found: {pptx_path}")
        sys.exit(1)

    if pdf_path is None:
        pdf_path = pptx_path.with_suffix(".pdf")
    pdf_path = Path(pdf_path)

    print(f"  Converting: {pptx_path.name}")

    # Try methods in order of quality
    soffice = find_libreoffice()
    if find_powerpoint():
        convert_with_powerpoint(pptx_path, pdf_path)
    elif soffice:
        convert_with_libreoffice(pptx_path, pdf_path, soffice)
    else:
        print("  WARNING: No PowerPoint or LibreOffice found.")
        print("  For best results, install LibreOffice (free): https://www.libreoffice.org/download/")
        print("  Using text-extraction fallback...\n")
        convert_with_python(pptx_path, pdf_path)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    target = Path(sys.argv[1])
    output = sys.argv[2] if len(sys.argv) > 2 else None

    if target.is_dir():
        pptx_files = sorted(target.glob("*.pptx"))
        if not pptx_files:
            print(f"  No .pptx files found in {target}")
            return
        print(f"\n  Found {len(pptx_files)} PPTX files in {target}\n")
        for f in pptx_files:
            convert(f)
        print(f"\n  Done! Converted {len(pptx_files)} files.\n")
    else:
        convert(target, output)
        print("  Done!\n")


if __name__ == "__main__":
    main()
