"""Encoding detection, text sanitation, and garbled-output checking.

Used by text extraction (merge, PDF) and image OCR to validate output quality and
recover readable text from files using non-UTF-8 encodings.
"""
from pathlib import Path


def read_text_safe(file: Path, fallback_encodings=None) -> tuple[str, str]:
    """Read a file as text, trying UTF-8 first then a set of common fallbacks.

    Returns (text, encoding_used).
    """
    fallback_encodings = list(fallback_encodings or []) or [
        "utf-8", "latin-1", "cp1252", "cp1250", "iso-8859-9", "cp1254",
        "iso-8859-1", "cp850", "utf-16", "utf-16-le", "utf-16-be",
    ]
    raw = file.read_bytes()
    errors = []

    for enc in fallback_encodings:
        try:
            # charset-normalizer gives a guaranteed result; use it for UTF-8+.
            if enc in ("utf-8",) and raw:
                try:
                    import charset_normalizer
                    match = charset_normalizer.from_bytes(raw).best()
                    if match:
                        return str(match), match.encoding
                except Exception:
                    pass
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            errors.append(enc)
            continue

    # Last resort: decode with replacement characters so we at least get *something*.
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def looks_corrupt(text: str) -> tuple[bool, str]:
    """Heuristic check: does the text look like garbage?

    Returns (is_corrupt, reason). Reason is empty if the text looks clean.
    """
    if not text or not text.strip():
        return True, "no selectable text"

    size = len(text)
    if size < 8:
        return False, ""  # too short to judge

    # Control characters (excluding common whitespace).
    control = sum(1 for c in text if ord(c) < 0x20 and c not in "\n\r\t")
    if control > size * 0.15:
        return True, f"{control} control characters ({control / size:.0%} of text)"

    # Unicode replacement chars from failed decoding.
    reps = text.count("\ufffd")
    if reps > 0 and reps > max(size // 80, 2):
        return True, f"{reps} replacement characters (likely wrong encoding)"

    # High proportion of non-printable bytes = binary data leaking through.
    non_print = sum(1 for c in text if not c.isprintable() and c not in "\n\r\t")
    if non_print > size * 0.08:
        return True, f"{non_print} non-printable characters"

    # Repeated same byte pattern (e.g. null-padding, binary blobs).
    from collections import Counter
    top = Counter(text).most_common(3)
    if top and top[0][1] > size * 0.4 and ord(top[0][0]) < 32:
        return True, f"dominated by '{top[0][0]!r}' ({top[0][1] / size:.0%})"

    return False, ""


def check_and_warn(text: str, label: str, console) -> bool:
    """Invoke `looks_corrupt` and print a warning to the console if needed.
    Returns True when text looks clean, False when corrupt.
    """
    corrupt, reason = looks_corrupt(text)
    if corrupt:
        console.print(f"  [yellow]⚠ {label}: output may be garbled — {reason}[/yellow]")
        console.print(f"  [dim]Try a different encoding or run the file through OCR instead.[/dim]")
    return not corrupt


def reencode_to_utf8(input_path: Path, console, output_path: Path | None = None) -> Path:
    """Detect a text file's encoding and re-save it as clean UTF-8 (fixes 'weird characters')."""
    out_path = output_path or (input_path.parent / f"{input_path.stem}_utf8{input_path.suffix}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold cyan]Detecting encoding of {input_path.name}…[/bold cyan]"):
        text, enc = read_text_safe(input_path)

    corrupt, reason = looks_corrupt(text)
    if corrupt:
        console.print(f"[yellow]⚠ This file still looks unreadable ({reason}); it may be binary or corrupted.[/yellow]")

    out_path.write_text(text, encoding="utf-8")
    console.print(
        f"[bold green]✓ Re-encoded[/bold green] [dim]{enc} → utf-8[/dim] → {out_path.name}"
    )
    return out_path

