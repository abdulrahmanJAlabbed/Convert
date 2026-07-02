import time
from pathlib import Path
from rich.console import Console
from faster_whisper import WhisperModel
import os

CACHE_DIR = Path(__file__).parent.parent / "model_cache"
CACHE_DIR.mkdir(exist_ok=True)
os.environ["HF_HOME"] = str(CACHE_DIR)

MODEL_SIZE = "large-v3"
DEVICE = "cpu"
COMPUTE = "int8"
BEAM_SIZE = 5

def fmt_time(s: float) -> str:
    ms = int((s % 1) * 1000)
    return f"{int(s)//3600:02d}:{(int(s)//60)%60:02d}:{int(s)%60:02d},{ms:03d}"

def transcribe(video: Path, target_format: str, console: Console):
    txt_path = video.with_suffix(f".{target_format}")
    
    with console.status(f"[bold cyan]Loading Whisper Model ({MODEL_SIZE} on {DEVICE})...[/bold cyan]") as status:
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE, download_root=str(CACHE_DIR))
        console.print("[green]Model loaded successfully![/green]")
        
        status.update(f"[bold yellow]Transcribing {video.name}...[/bold yellow]")
        
        t0 = time.time()
        segments, info = model.transcribe(
            str(video),
            beam_size=BEAM_SIZE,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        
        console.print(f"Detected Language: [bold]{info.language}[/bold] ({info.language_probability:.0%})")
        console.print(f"Duration: [bold]{info.duration:.1f}s[/bold]")
        
        with open(txt_path, "w", encoding="utf-8") as out_f:
            for i, seg in enumerate(segments, start=1):
                text = seg.text.strip()
                
                # Write to file based on target format
                if target_format == "txt":
                    out_f.write(text + "\n")
                elif target_format == "srt":
                    out_f.write(f"{i}\n{fmt_time(seg.start)} --> {fmt_time(seg.end)}\n{text}\n\n")
                    
                out_f.flush()
                # Print real-time progress to console (trimming text so it doesn't clutter)
                display_text = text if len(text) < 50 else text[:47] + "..."
                console.print(f"  [dim]{fmt_time(seg.start)}[/dim] {display_text}")

        elapsed = time.time() - t0
        speed = info.duration / elapsed if elapsed else 0
        console.print(f"\n[bold green]✓ Done in {elapsed/60:.1f} min ({speed:.1f}x real-time)[/bold green]")
        console.print(f"Saved to: [bold underline]{txt_path.name}[/bold underline]")
