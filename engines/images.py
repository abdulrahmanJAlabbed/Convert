from pathlib import Path
from rich.console import Console
from PIL import Image
import easyocr

# Initialize reader globally but lazily
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'])
    return _reader

def convert_image(input_path: Path, target_format: str, console: Console):
    if target_format == "txt":
        # OCR
        with console.status(f"[bold cyan]Running OCR on {input_path.name}...[/bold cyan]"):
            reader = get_reader()
            results = reader.readtext(str(input_path), detail=0)
            text = "\n".join(results)
            
            out_path = input_path.with_suffix(".txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
                
            console.print(f"[bold green]✓ OCR completed! Saved to {out_path.name}[/bold green]")
            
    elif target_format in ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "ico"]:
        # Format conversion
        with console.status(f"[bold cyan]Converting image to {target_format.upper()}...[/bold cyan]"):
            img = Image.open(input_path)
            # Handle alpha channel if saving to jpeg
            if target_format in ["jpg", "jpeg"] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            out_path = input_path.with_suffix(f".{target_format}")
            img.save(out_path)
            console.print(f"[bold green]✓ Converted! Saved to {out_path.name}[/bold green]")
    else:
        raise ValueError(f"Cannot convert image to {target_format}")


def resize_image(input_path: Path, width: int | None, height: int | None, console: Console):
    """Resize an image. If only one dimension is given, the other scales proportionally."""
    img = Image.open(input_path)
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
        img = img.resize(new_size, Image.LANCZOS)

        out_path = input_path.parent / f"{input_path.stem}_resized{input_path.suffix}"
        # Handle alpha channel for jpeg
        if input_path.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(out_path)

    console.print(f"[bold green]✓ Resized! {original_w}x{original_h} → {new_size[0]}x{new_size[1]}[/bold green]")
    console.print(f"Saved to: [bold underline]{out_path.name}[/bold underline]")


def compress_image(input_path: Path, quality: int, console: Console):
    """Compress an image by reducing quality (1-100). Lower = smaller file."""
    img = Image.open(input_path)
    original_size = input_path.stat().st_size

    out_path = input_path.parent / f"{input_path.stem}_compressed{input_path.suffix}"

    # Handle alpha channel for jpeg
    if input_path.suffix.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    with console.status(f"[bold cyan]Compressing {input_path.name} (quality={quality})…[/bold cyan]"):
        save_kwargs = {"optimize": True}
        ext = input_path.suffix.lower()

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


def image_to_pdf(input_path: Path, console: Console):
    """Convert a single image to a PDF document."""
    img = Image.open(input_path).convert("RGB")
    out_path = input_path.with_suffix(".pdf")

    with console.status(f"[bold cyan]Converting {input_path.name} to PDF…[/bold cyan]"):
        img.save(out_path)

    console.print(f"[bold green]✓ Created {out_path.name}[/bold green]")
