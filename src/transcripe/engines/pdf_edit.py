"""PDF editing engine — edit-in-browser, find & replace, layout-true Word export.

Ported and generalized from the cv_editor toolkit:

    editable_html()     any PDF -> editable HTML that KEEPS the original design.
                        Text-layer pages use exact PyMuPDF spans (position, size,
                        color, bold — no OCR). Scanned pages fall back to OCR
                        boxes. Baked-in text is erased by painting each box with
                        its sampled background color; an editable overlay div is
                        placed on top. Open in a browser, click any text, print
                        to PDF.
    find_replace()      redact + reinsert text on text-layer PDFs (RTL-aware).
    extract_images()    dump embedded raster images.
    pdf_to_docx_layout() layout-preserving PDF -> Word via pdf2docx.
    make_searchable()   add an invisible OCR text layer via OCRmyPDF.

All heavy imports are lazy so CLI startup stays instant.
"""
from __future__ import annotations

import base64
import html as _html
import io
from pathlib import Path

from rich.console import Console

# ── RTL helpers (Arabic/Hebrew/Farsi) ───────────────────────────────────────

RTL_RANGES = ((0x0590, 0x05FF), (0x0600, 0x06FF), (0x0750, 0x077F),
              (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def is_rtl(text: str) -> bool:
    return any(a <= ord(ch) <= b for ch in text for a, b in RTL_RANGES)


def shape_rtl(text: str) -> str:
    """Reshape + reorder Arabic so PDF engines draw it correctly.
    Returns text unchanged when not RTL or the libs are missing."""
    if not is_rtl(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _esc(s: str) -> str:
    return _html.escape(s, quote=False)


# ── background/text color sampling (for erasing baked-in text) ──────────────

def _sample_colors(arr, x0, y0, x1, y1):
    """Return (bg_rgb, text_rgb) for a box region of an HxWx3 numpy image."""
    import numpy as np
    h, w = arr.shape[:2]
    x0i, y0i = max(0, int(x0)), max(0, int(y0))
    x1i, y1i = min(w, int(x1)), min(h, int(y1))
    if x1i <= x0i or y1i <= y0i:
        return (255, 255, 255), (0, 0, 0)
    pad = 4  # background = median of a thin ring just outside the box
    rx0, ry0 = max(0, x0i - pad), max(0, y0i - pad)
    rx1, ry1 = min(w, x1i + pad), min(h, y1i + pad)
    ring = arr[ry0:ry1, rx0:rx1].reshape(-1, 3)
    bg = np.median(ring, axis=0)
    inside = arr[y0i:y1i, x0i:x1i].reshape(-1, 3)
    lum = inside @ np.array([0.299, 0.587, 0.114])
    bglum = float(bg @ np.array([0.299, 0.587, 0.114]))
    txt = inside[int(np.argmax(np.abs(lum - bglum)))]
    return tuple(int(v) for v in bg), tuple(int(v) for v in txt)


# ── editable HTML (design-preserving) ───────────────────────────────────────

SHEET_W = 794  # A4 width @96dpi → clean print scale

EDIT_TPL = """<!doctype html><html dir="{d}" lang="{lang}"><head><meta charset="utf-8">
<title>{title}</title><style>
:root{{color-scheme:light}}
body{{margin:0;background:#525659;font-family:'Noto Sans Arabic','Segoe UI',Arial,sans-serif}}
.bar{{position:sticky;top:0;z-index:9;background:#143d36;color:#fff;padding:.5rem 1rem;font-size:.85rem}}
.bar button{{background:#fff;color:#143d36;border:0;border-radius:5px;padding:.3rem .7rem;cursor:pointer;font-weight:700}}
.sheet{{position:relative;margin:1.2rem auto;background:#fff;box-shadow:0 3px 14px rgba(0,0,0,.4)}}
.sheet img{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;user-select:none}}
.t{{position:absolute;white-space:pre;line-height:1.15;outline:none;overflow:visible}}
.t:focus{{box-shadow:0 0 0 2px #2f81f7}}
.t.b{{font-weight:700}}
*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media print{{.bar{{display:none}}body{{background:#fff}}
  .sheet{{box-shadow:none;margin:0;page-break-after:always;break-after:page}}
  @page{{size:{pw}px {ph}px;margin:0}}}}
</style></head><body>
<div class="bar">✎ Click any text to edit · design preserved ·
<button onclick="window.print()">Save as PDF</button></div>
{pages}
</body></html>"""


def _text_layer_boxes(page, zoom: float):
    """Extract (x0,y0,x1,y1,text,size_px,color_css,bold) spans from a text page."""
    out = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text.strip():
                    continue
                x0, y0, x1, y1 = (v * zoom for v in span["bbox"])
                size = span.get("size", 11) * zoom
                color = f"#{span.get('color', 0):06x}"
                bold = bool(span.get("flags", 0) & 16)
                out.append((x0, y0, x1, y1, text, size, color, bold))
    return out


def _ocr_layer_boxes(pil_img, langs):
    """OCR boxes for image-only pages: (x0,y0,x1,y1,text,size_px,color,bold)."""
    from transcripe.engines import ocr
    boxes = ocr.ocr_boxes(pil_img, langs)
    out = []
    for (x0, y0, x1, y1, text) in boxes:
        fs = max(8.0, (y1 - y0) * 0.78)
        out.append((x0, y0, x1, y1, text, fs, None, False))  # color sampled later
    return out


def editable_html(pdf_path: Path, console: Console, output_path: Path | None = None,
                  langs: list[str] | None = None) -> Path:
    """Convert any PDF into a design-preserving editable HTML file."""
    import fitz  # PyMuPDF
    import numpy as np
    from PIL import Image, ImageDraw

    out_path = output_path or (pdf_path.parent / f"{pdf_path.stem}_editable.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    pages_html = []
    all_text = []
    ph_out = 1123
    for i, pg in enumerate(doc):
        zoom = SHEET_W / pg.rect.width
        pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        W, H = img.size
        ph_out = H

        has_text = bool(pg.get_text("text").strip())
        if has_text:
            console.print(f"  [dim]page {i + 1}: text layer → exact spans[/dim]")
            boxes = _text_layer_boxes(pg, zoom)
        else:
            console.print(f"  [dim]page {i + 1}: scanned → OCR boxes[/dim]")
            boxes = _ocr_layer_boxes(img, langs)

        arr = np.asarray(img).copy()
        draw = ImageDraw.Draw(img)
        divs = []
        for (x0, y0, x1, y1, text, fs, color, bold) in boxes:
            bg, sampled = _sample_colors(arr, x0, y0, x1, y1)
            # Erase the baked-in text: paint the box with its background color
            # (with a small bleed so no ghost pixels survive).
            bh = (y1 - y0) * 0.18
            draw.rectangle([x0 - 2, y0 - bh, x1 + 2, y1 + bh], fill=bg)
            css_color = color if color else f"rgb{sampled}"
            rtl = is_rtl(text)
            style = (f"left:{x0:.0f}px;top:{y0:.0f}px;"
                     f"width:{(x1 - x0):.0f}px;height:{(y1 - y0):.0f}px;"
                     f"font-size:{fs:.1f}px;color:{css_color};"
                     f"display:flex;align-items:center;"
                     f"justify-content:{'flex-end' if rtl else 'flex-start'};"
                     f"direction:{'rtl' if rtl else 'ltr'}")
            cls = "t b" if bold else "t"
            divs.append(f'<div class="{cls}" contenteditable style="{style}">{_esc(text)}</div>')
            all_text.append(text)

        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88)
        b64 = base64.b64encode(buf.getvalue()).decode()
        pages_html.append(
            f'<div class="sheet" style="width:{W}px;height:{H}px">'
            f'<img src="data:image/jpeg;base64,{b64}">' + "".join(divs) + "</div>")
    doc.close()

    joined = " ".join(all_text)
    html = EDIT_TPL.format(
        d="rtl" if is_rtl(joined) else "ltr",
        lang="ar" if is_rtl(joined) else "en",
        title=pdf_path.stem, pw=SHEET_W, ph=ph_out,
        pages="\n".join(pages_html))
    out_path.write_text(html, encoding="utf-8")
    console.print(f"[bold green]✓ Editable HTML created → {out_path.name}[/bold green]")
    console.print("[dim]Open in a browser → click any text to edit → 'Save as PDF' button,[/dim]")
    console.print(f"[dim]or finish from the terminal:  transcripe pdf render \"{out_path.name}\"[/dim]")
    return out_path


# ── HTML → PDF (round-trip for the editable-HTML workflow) ──────────────────

_CHROMIUM_NAMES = ("chromium", "chromium-browser", "google-chrome",
                   "google-chrome-stable", "chrome", "brave-browser", "msedge")


def _find_chromium() -> str | None:
    import shutil
    for name in _CHROMIUM_NAMES:
        p = shutil.which(name)
        if p:
            return p
    return None


def html_to_pdf(html_path: Path, console: Console, output_path: Path | None = None) -> Path:
    """Render an (edited) HTML file back to PDF.

    Chromium-family headless print first — pixel-perfect for the absolute-
    positioned editable pages — with WeasyPrint as the fallback renderer.
    """
    import subprocess
    import tempfile

    out_path = output_path or html_path.with_suffix(".pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chromium = _find_chromium()
    if chromium:
        with console.status(f"[bold cyan]Printing {html_path.name} → PDF (Chromium)…[/bold cyan]"):
            with tempfile.TemporaryDirectory(prefix="chrome_pdf_") as profile:
                result = subprocess.run(
                    [chromium, "--headless=new", "--disable-gpu", "--no-sandbox",
                     f"--user-data-dir={profile}",
                     "--no-pdf-header-footer",
                     f"--print-to-pdf={out_path}",
                     html_path.resolve().as_uri()],
                    capture_output=True, text=True, timeout=120,
                )
        if result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            console.print(f"[bold green]✓ PDF created → {out_path.name}[/bold green] [dim](Chromium)[/dim]")
            return out_path
        console.print("[yellow]Chromium print failed; trying WeasyPrint…[/yellow]")

    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            "HTML→PDF needs a Chromium-family browser or WeasyPrint "
            "(pip install 'transcripe[docs]')") from e
    with console.status(f"[bold cyan]Rendering {html_path.name} → PDF (WeasyPrint)…[/bold cyan]"):
        HTML(filename=str(html_path)).write_pdf(str(out_path))
    console.print(f"[bold green]✓ PDF created → {out_path.name}[/bold green] [dim](WeasyPrint)[/dim]")
    return out_path


# ── find & replace ──────────────────────────────────────────────────────────

def find_replace(pdf_path: Path, replacements: list[dict], console: Console,
                 output_path: Path | None = None) -> Path:
    """Find/replace text on a text-layer PDF.

    replacements: [{"find": str, "to": str, "size": float?}, ...]
    Finds all boxes first (text vanishes after redaction), then redacts, then
    redraws with shrink-to-fit so replacements are never silently dropped.
    """
    import fitz

    out_path = output_path or (pdf_path.parent / f"{pdf_path.stem}_edited.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    hits = []  # (page_index, rect, rule)
    for pi, pg in enumerate(doc):
        for rule in replacements:
            for inst in pg.search_for(rule["find"]):
                hits.append((pi, inst, rule))

    if not hits:
        doc.close()
        raise RuntimeError(
            "No matches found. (Scanned/image PDFs have no text layer — "
            "use '✏️ Edit PDF in browser' instead.)")

    for pi, rect, _ in hits:
        doc[pi].add_redact_annot(rect, fill=(1, 1, 1))
    for pg in doc:
        pg.apply_redactions()

    for pi, rect, rule in hits:
        pg = doc[pi]
        txt = shape_rtl(rule["to"])
        rtl = is_rtl(rule["to"])
        # give the box room to grow (replacement may be longer than the match)
        box = fitz.Rect(rect.x0 - (60 if rtl else 0), rect.y0 - 1,
                        rect.x1 + (0 if rtl else 60), rect.y1 + 4)
        size = float(rule.get("size") or 10)
        while size >= 5:  # shrink until it fits
            if pg.insert_textbox(box, txt, fontsize=size,
                                 align=2 if rtl else 0, color=(0, 0, 0)) >= 0:
                break
            size -= 0.5
        console.print(f"  [dim]page {pi + 1}: '{rule['find']}' → '{rule['to']}'[/dim]")

    doc.save(str(out_path), garbage=3, deflate=True)
    doc.close()
    console.print(f"[bold green]✓ Applied {len(hits)} replacement(s) → {out_path.name}[/bold green]")
    return out_path


# ── embedded image extraction ───────────────────────────────────────────────

def extract_images(pdf_path: Path, out_dir: Path | None, console: Console) -> Path:
    """Dump the raster images embedded in a PDF."""
    import fitz

    out_dir = out_dir or (pdf_path.parent / f"{pdf_path.stem}_images")
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    n = 0
    for i, pg in enumerate(doc):
        for j, img in enumerate(pg.get_images(full=True)):
            xref = img[0]
            d = doc.extract_image(xref)
            fn = out_dir / f"page{i + 1}_img{j + 1}.{d['ext']}"
            fn.write_bytes(d["image"])
            n += 1
            console.print(f"  [dim]+ {fn.name} ({d['width']}x{d['height']})[/dim]")
    doc.close()
    if n == 0:
        console.print("[yellow]No embedded raster images found in this PDF.[/yellow]")
    else:
        console.print(f"[bold green]✓ Extracted {n} image(s) → {out_dir.name}/[/bold green]")
    return out_dir


# ── layout-preserving PDF → Word ────────────────────────────────────────────

def pdf_to_docx_layout(pdf_path: Path, console: Console,
                       output_path: Path | None = None) -> Path:
    """PDF → .docx keeping layout (tables, columns, images) via pdf2docx."""
    from pdf2docx import Converter

    out_path = output_path or pdf_path.with_suffix(".docx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Rebuilding {pdf_path.name} as Word (layout-preserving)…[/bold cyan]"):
        cv = Converter(str(pdf_path))
        try:
            cv.convert(str(out_path))
        finally:
            cv.close()

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("pdf2docx produced no output")
    console.print(f"[bold green]✓ Created {out_path.name}[/bold green] [dim](layout preserved)[/dim]")
    return out_path


# ── searchable PDF (OCR text layer) ─────────────────────────────────────────

# language-code map: transcripe/EasyOCR codes → tesseract codes
_TESS_LANG = {"en": "eng", "tr": "tur", "ar": "ara", "ch_sim": "chi_sim",
              "fr": "fra", "de": "deu", "es": "spa", "it": "ita", "pt": "por",
              "ru": "rus", "ja": "jpn", "ko": "kor", "nl": "nld", "pl": "pol"}


def _installed_tess_langs() -> set[str]:
    """Language packs the local tesseract actually has (empty set if unknown)."""
    import shutil
    import subprocess
    tess = shutil.which("tesseract")
    if not tess:
        return set()
    try:
        out = subprocess.run([tess, "--list-langs"], capture_output=True, text=True, timeout=10)
        return {l.strip() for l in out.stdout.splitlines()[1:] if l.strip()}
    except Exception:
        return set()


def make_searchable(pdf_path: Path, console: Console, output_path: Path | None = None,
                    langs: list[str] | None = None) -> Path:
    """Add an invisible OCR text layer to a scanned PDF (output stays visually identical).

    Pages OCR in parallel (one job per CPU core) and the output is losslessly
    optimized. Requested languages are validated against the installed
    tesseract packs so a missing pack degrades instead of failing the run.
    """
    import os
    import ocrmypdf

    out_path = output_path or (pdf_path.parent / f"{pdf_path.stem}_searchable.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wanted = [_TESS_LANG.get(l, l) for l in (langs or ["en"])]
    installed = _installed_tess_langs()
    if installed:
        usable = [l for l in wanted if l in installed]
        skipped = [l for l in wanted if l not in installed]
        if skipped:
            console.print(
                f"[yellow]⚠ tesseract pack(s) missing: {', '.join(skipped)} "
                f"(install tesseract-ocr-<lang>); continuing with: "
                f"{', '.join(usable) or 'eng'}[/yellow]")
        wanted = usable or (["eng"] if "eng" in installed else list(installed)[:1])
    language = "+".join(wanted)

    jobs = os.cpu_count() or 1
    with console.status(f"[bold cyan]OCR'ing {pdf_path.name} → searchable PDF "
                        f"({language}, {jobs} parallel jobs)…[/bold cyan]"):
        ocrmypdf.ocr(str(pdf_path), str(out_path), language=language,
                     skip_text=True, progress_bar=False,
                     jobs=jobs, optimize=1)

    console.print(f"[bold green]✓ Searchable PDF created → {out_path.name}[/bold green]")
    console.print("[dim]Looks identical, but text is now selectable & searchable.[/dim]")
    return out_path
