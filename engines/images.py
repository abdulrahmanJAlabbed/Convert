from pathlib import Path
from rich.console import Console
from PIL import Image
import easyocr
import io

# Initialize reader globally but lazily if possible, or just initialize when needed.
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
            
    elif target_format in ["png", "jpg", "jpeg", "webp"]:
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
