from pathlib import Path
from rich.console import Console
from transcripe.engines import ocr

_HEIF_REGISTERED = False


def _pil():
    """Lazy Pillow import (images extra) + one-time HEIC/AVIF plugin registration."""
    global _HEIF_REGISTERED
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError(
            "Image operations need Pillow — pip install 'transcripe[images]'") from e
    if not _HEIF_REGISTERED:
        _HEIF_REGISTERED = True
        try:
            from pillow_heif import register_heif_opener, register_avif_opener
            register_heif_opener()
            register_avif_opener()
        except ImportError:
            pass
    return Image


def _open_image(input_path: Path):
    """Open any supported image; rasterizes SVG (Pillow can't read vectors)."""
    Image = _pil()
    if input_path.suffix.lower() == ".svg":
        try:
            import cairosvg
        except ImportError:
            raise RuntimeError(
                "SVG input needs 'cairosvg' — pip install cairosvg "
                "(requires the system cairo library)")
        import io
        png_bytes = cairosvg.svg2png(url=str(input_path))
        return Image.open(io.BytesIO(png_bytes))
    try:
        return Image.open(input_path)
    except Exception as e:
        ext = input_path.suffix.lower()
        if ext in (".heic", ".avif"):
            raise RuntimeError(
                f"Cannot open {ext} — install the HEIF plugin: pip install pillow-heif") from e
        raise


def get_reader():
    """Backwards-compatible EasyOCR reader accessor (prefer engines.ocr.ocr_image)."""
    return ocr._get_easy(("en",))

def convert_image(input_path: Path, target_format: str, console: Console,
                  output_path: Path | None = None, langs: list[str] | None = None):
    if target_format == "txt":
        # OCR
        engine = ocr.available_engine(langs)
        lang_label = ", ".join(langs) if langs else "auto"
        with console.status(f"[bold cyan]Running OCR on {input_path.name} ({engine}, {lang_label})…[/bold cyan]"):
            text = ocr.ocr_image(input_path, langs)

            out_path = output_path or input_path.with_suffix(".txt")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)

            console.print(f"[bold green]✓ OCR completed! Saved to {out_path.name}[/bold green] [dim]({len(text)} chars)[/dim]")

    elif target_format in ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "ico"]:
        # Format conversion
        with console.status(f"[bold cyan]Converting image to {target_format.upper()}...[/bold cyan]"):
            img = _open_image(input_path)
            # Handle alpha channel if saving to jpeg
            if target_format in ["jpg", "jpeg"] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            out_path = output_path or input_path.with_suffix(f".{target_format}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path)
            console.print(f"[bold green]✓ Converted! Saved to {out_path.name}[/bold green]")
    else:
        raise ValueError(f"Cannot convert image to {target_format}")


def resize_image(input_path: Path, width: int | None, height: int | None, console: Console, output_path: Path | None = None):
    """Resize an image. If only one dimension is given, the other scales proportionally."""
    img = _open_image(input_path)
    original_w, original_h = img.size

    if width and height:
        new_size = (width, height)
    elif width:
        ratio = width / original_w
        new_size = (width, int(original_h * ratio))
    elif height:
        ratio = height / original_h
        new_size = (int(original_w * ratio), height)
    else:
        console.print("[red]Please specify a width or height.[/red]")
        return

    with console.status(f"[bold cyan]Resizing {input_path.name} ({original_w}x{original_h} → {new_size[0]}x{new_size[1]})…[/bold cyan]"):
        img = img.resize(new_size, _pil().LANCZOS)

        out_path = output_path or (input_path.parent / f"{input_path.stem}_resized{input_path.suffix}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Handle alpha channel for jpeg
        if out_path.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(out_path)

    console.print(f"[bold green]✓ Resized! {original_w}x{original_h} → {new_size[0]}x{new_size[1]}[/bold green]")
    console.print(f"Saved to: [bold underline]{out_path.name}[/bold underline]")


def compress_image(input_path: Path, quality: int, console: Console, output_path: Path | None = None):
    """Compress an image by reducing quality (1-100). Lower = smaller file."""
    img = _open_image(input_path)
    original_size = input_path.stat().st_size

    out_path = output_path or (input_path.parent / f"{input_path.stem}_compressed{input_path.suffix}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle alpha channel for jpeg
    if out_path.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    with console.status(f"[bold cyan]Compressing {input_path.name} (quality={quality})…[/bold cyan]"):
        save_kwargs = {"optimize": True}
        ext = out_path.suffix.lower()

        if ext in (".jpg", ".jpeg"):
            save_kwargs["quality"] = quality
        elif ext == ".png":
            save_kwargs["compress_level"] = min(9, max(0, (100 - quality) // 10))
        elif ext == ".webp":
            save_kwargs["quality"] = quality

        img.save(out_path, **save_kwargs)

    new_size = out_path.stat().st_size
    reduction = (1 - new_size / original_size) * 100 if original_size > 0 else 0
    orig_kb = original_size / 1024
    new_kb = new_size / 1024
    console.print(f"[bold green]✓ Compressed! {orig_kb:.0f} KB → {new_kb:.0f} KB ({reduction:.0f}% smaller)[/bold green]")
    console.print(f"Saved to: [bold underline]{out_path.name}[/bold underline]")


def image_to_pdf(input_path: Path, console: Console, output_path: Path | None = None):
    """Convert a single image to a PDF document."""
    img = _open_image(input_path).convert("RGB")
    out_path = output_path or input_path.with_suffix(".pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Converting {input_path.name} to PDF…[/bold cyan]"):
        img.save(out_path)

    console.print(f"[bold green]✓ Created {out_path.name}[/bold green]")
