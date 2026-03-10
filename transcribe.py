"""
Batch Video Transcription - Whisper large-v3 (CPU int8)
=======================================================
Processes all .mp4 files in this folder one by one.
Outputs per video:
  * <name>.txt  - plain text transcript
  * <name>.srt  - subtitles with timestamps

Model  : openai/whisper-large-v3 (best free ASR model)
Backend: faster-whisper (much faster than original Whisper)
Device : CPU + int8  (GPU needs CUDA Toolkit installed separately)

NOTE: Model cache is stored in this same folder under 'model_cache'.
"""

import sys, io, os, time
from pathlib import Path

# Force UTF-8 output so special chars print correctly on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Keep model cache in the same folder as the videos (easy to manage/delete)
SCRIPT_DIR   = Path(__file__).parent
CACHE_DIR    = SCRIPT_DIR / "model_cache"
CACHE_DIR.mkdir(exist_ok=True)
os.environ["HF_HOME"] = str(CACHE_DIR)

from faster_whisper import WhisperModel

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_SIZE = "large-v3"   # Best available Whisper model
DEVICE     = "cpu"        # "cuda" requires CUDA Toolkit 12.x installed
COMPUTE    = "int8"       # int8 = fast CPU inference, low RAM
LANGUAGE   = None         # None = auto-detect; or e.g. "en", "ar"
BEAM_SIZE  = 5
# ──────────────────────────────────────────────────────────────────────────────


def fmt_time(s: float) -> str:
    ms = int((s % 1) * 1000)
    return f"{int(s)//3600:02d}:{(int(s)//60)%60:02d}:{int(s)%60:02d},{ms:03d}"


def transcribe_video(model: WhisperModel, video: Path):
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  File : {video.name}  ({video.stat().st_size / 1e6:.0f} MB)")
    print(sep)

    txt_path = video.with_suffix(".txt")
    srt_path = video.with_suffix(".srt")

    t0 = time.time()
    segments, info = model.transcribe(
        str(video),
        beam_size=BEAM_SIZE,
        language=LANGUAGE,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    print(f"  Language : {info.language} ({info.language_probability:.0%})")
    print(f"  Duration : {info.duration:.1f}s\n")

    # Write incrementally so files grow in real-time while transcribing
    with open(txt_path, "w", encoding="utf-8") as txt_f, \
         open(srt_path, "w", encoding="utf-8") as srt_f:

        for i, seg in enumerate(segments, start=1):
            text = seg.text.strip()
            # Console progress
            print(f"  [{fmt_time(seg.start)} --> {fmt_time(seg.end)}]  {text}")
            # .txt (plain)
            txt_f.write(text + "\n")
            txt_f.flush()
            # .srt
            srt_f.write(f"{i}\n{fmt_time(seg.start)} --> {fmt_time(seg.end)}\n{text}\n\n")
            srt_f.flush()

    elapsed = time.time() - t0
    speed   = info.duration / elapsed if elapsed else 0
    print(f"\n  Done in {elapsed/60:.1f} min  ({speed:.1f}x real-time)")
    print(f"  --> {txt_path.name}")
    print(f"  --> {srt_path.name}")


def main():
    videos = sorted(SCRIPT_DIR.glob("*.mp4"))
    if not videos:
        print("No .mp4 files found.")
        return

    print(f"\n{'='*60}")
    print(f"  Loading Whisper {MODEL_SIZE} on {DEVICE.upper()} ...")
    print(f"  Model cache : {CACHE_DIR}")
    if not any(CACHE_DIR.iterdir()) if CACHE_DIR.exists() else True:
        print(f"  (First run downloads ~3 GB model, please wait)")
    print(f"{'='*60}")

    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE,
                         download_root=str(CACHE_DIR))
    print("  Model loaded!\n")

    total_t = time.time()
    for i, vid in enumerate(videos, 1):
        print(f"\n[Video {i}/{len(videos)}]", end="")
        transcribe_video(model, vid)

    print(f"\n\n{'='*60}")
    print(f"  All {len(videos)} videos done in {(time.time()-total_t)/60:.1f} minutes.")
    print(f"  Transcripts saved next to each video.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
