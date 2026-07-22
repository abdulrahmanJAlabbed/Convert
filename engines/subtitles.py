"""Subtitle engine: SRT ↔ VTT ↔ ASS conversion, plain-text export, burn-in.

Pure-python parsing/writing (no deps); burn-in uses FFmpeg.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".ssa"}
SUBTITLE_TARGETS = {"srt", "vtt", "ass", "txt"}


@dataclass
class Cue:
    start: float  # seconds
    end: float
    text: str     # may contain \n


# ── time helpers ────────────────────────────────────────────────────────────

def _parse_time(s: str) -> float:
    """Parse 'HH:MM:SS,mmm' / 'HH:MM:SS.mmm' / 'MM:SS.mmm' / 'H:MM:SS.cc' to seconds."""
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) == 2:
        parts = ["0"] + parts
    h, m, sec = parts
    return int(h) * 3600 + int(m) * 60 + float(sec)


def _srt_time(t: float) -> str:
    ms = round((t % 1) * 1000)
    return f"{int(t) // 3600:02d}:{(int(t) // 60) % 60:02d}:{int(t) % 60:02d},{ms:03d}"


def _vtt_time(t: float) -> str:
    return _srt_time(t).replace(",", ".")


def _ass_time(t: float) -> str:
    cs = round((t % 1) * 100)
    return f"{int(t) // 3600}:{(int(t) // 60) % 60:02d}:{int(t) % 60:02d}.{cs:02d}"


# ── parsers ─────────────────────────────────────────────────────────────────

_TIMELINE = re.compile(r"([\d:.,]+)\s*-->\s*([\d:.,]+)")


def _parse_srt_vtt(text: str) -> list[Cue]:
    """Parse SRT or WebVTT (both use 'start --> end' timing lines)."""
    cues: list[Cue] = []
    block: list[str] = []

    def flush(blk):
        for i, line in enumerate(blk):
            m = _TIMELINE.search(line)
            if m:
                body = "\n".join(blk[i + 1:]).strip()
                # strip inline tags (<i>, <b>, VTT <c.class>…)
                body = re.sub(r"</?[^>]+>", "", body)
                if body:
                    cues.append(Cue(_parse_time(m.group(1)), _parse_time(m.group(2)), body))
                return

    for line in text.splitlines():
        if not line.strip():
            if block:
                flush(block)
                block = []
        else:
            block.append(line)
    if block:
        flush(block)
    return cues


_ASS_DIALOGUE = re.compile(r"^Dialogue:\s*[^,]*,([^,]+),([^,]+),", re.M)


def _parse_ass(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        start, end, body = parts[1], parts[2], parts[9]
        body = re.sub(r"\{[^}]*\}", "", body)          # strip {\pos…} override tags
        body = body.replace("\\N", "\n").replace("\\n", "\n").strip()
        if body:
            cues.append(Cue(_parse_time(start), _parse_time(end), body))
    return cues


def parse(path: Path) -> list[Cue]:
    from core import text_utils
    text, _enc = text_utils.read_text_safe(path)
    ext = path.suffix.lower()
    if ext in (".ass", ".ssa"):
        cues = _parse_ass(text)
    else:
        cues = _parse_srt_vtt(text)
    if not cues:
        raise RuntimeError(f"No subtitle cues found in {path.name}")
    return cues


# ── writers ─────────────────────────────────────────────────────────────────

def to_srt(cues: list[Cue]) -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{_srt_time(c.start)} --> {_srt_time(c.end)}\n{c.text}\n")
    return "\n".join(out)


def to_vtt(cues: list[Cue]) -> str:
    out = ["WEBVTT", ""]
    for c in cues:
        out.append(f"{_vtt_time(c.start)} --> {_vtt_time(c.end)}\n{c.text}\n")
    return "\n".join(out)


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, Outline, Shadow
Style: Default,Arial,48,&H00FFFFFF,&H00000000,&H64000000,0,0,2,60,60,40,2,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def to_ass(cues: list[Cue]) -> str:
    lines = [_ASS_HEADER]
    for c in cues:
        body = c.text.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Default,,0,0,0,,{body}")
    return "\n".join(lines) + "\n"


def to_txt(cues: list[Cue]) -> str:
    return "\n".join(c.text for c in cues) + "\n"


_WRITERS = {"srt": to_srt, "vtt": to_vtt, "ass": to_ass, "txt": to_txt}


def convert_subtitle(input_path: Path, target: str, console: Console,
                     output_path: Path | None = None) -> Path:
    """Convert between subtitle formats (or strip timing with target 'txt')."""
    target = target.lower().lstrip(".")
    if target not in _WRITERS:
        raise ValueError(f"Cannot convert subtitles to .{target} (srt/vtt/ass/txt)")
    cues = parse(input_path)
    out_path = output_path or input_path.with_suffix(f".{target}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_WRITERS[target](cues), encoding="utf-8")
    console.print(f"[bold green]✓ {len(cues)} cues → {out_path.name}[/bold green]")
    return out_path


# ── burn-in ─────────────────────────────────────────────────────────────────

def burn_subtitles(video: Path, subs: Path, console: Console,
                   output_path: Path | None = None) -> Path:
    """Hard-burn subtitles into a video (re-encodes the video track)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg not found! Please install FFmpeg.")

    out_path = output_path or (video.parent / f"{video.stem}_subtitled{video.suffix}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg subtitles filter: escape ' : \ in the filename argument
    sub_arg = str(subs).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    with console.status(f"[bold cyan]Burning {subs.name} into {video.name}…[/bold cyan]"):
        result = subprocess.run(
            [ffmpeg, "-i", str(video), "-vf", f"subtitles='{sub_arg}'",
             "-codec:a", "copy", "-y", str(out_path)],
            capture_output=True, text=True,
        )
    if result.returncode != 0:
        err = result.stderr.strip().splitlines()[-1] if result.stderr else "unknown error"
        raise RuntimeError(f"FFmpeg failed: {err}")

    size_mb = out_path.stat().st_size / 1_048_576
    console.print(f"[bold green]✓ Subtitled video → {out_path.name} ({size_mb:.1f} MB)[/bold green]")
    return out_path
