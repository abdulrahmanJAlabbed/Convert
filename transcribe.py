"""
Batch Video Transcription - Whisper large-v3 (GPU)
===================================================
Reads .mp4 files from input/ and writes transcripts to output/.
"""

import sys, io, os, time, json
from pathlib import Path

# UTF-8 console on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Register CUDA DLLs from pip nvidia packages ─────────────────────────────
import site
for sp in site.getsitepackages():
    nvidia_dir = Path(sp) / "nvidia"
    if nvidia_dir.is_dir():
        for pkg in nvidia_dir.iterdir():
            dll_dir = pkg / "bin"
            if dll_dir.is_dir():
                os.add_dll_directory(str(dll_dir))
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR   = Path(__file__).parent
INPUT_DIR  = ROOT_DIR / "input"
OUTPUT_DIR = ROOT_DIR / "output"
CACHE_DIR  = ROOT_DIR / "model_cache"

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
os.environ["HF_HOME"] = str(CACHE_DIR)

from faster_whisper import WhisperModel

# ── Configuration ─────────────────────────────────────────────────────────────
MODEL_SIZE = "large-v3"
DEVICE     = "cuda"       # auto-falls back to CPU
COMPUTE    = "float16"    # float16 for GPU; int8 for CPU
LANGUAGE   = None         # None = auto-detect
BEAM_SIZE  = 5
# ─────────────────────────────────────────────────────────────────────────────

STATUS_FILE = ROOT_DIR / "status.json"


def save_status(data):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fmt_ts(s: float) -> str:
    ms = int((s % 1) * 1000)
    return f"{int(s)//3600:02d}:{(int(s)//60)%60:02d}:{int(s)%60:02d},{ms:03d}"


def transcribe_video(model, video, vid_idx, total_vids, status):
    name = video.name
    stem = video.stem
    sep = "=" * 60
    print(f"\n{sep}\n  [{vid_idx}/{total_vids}]  {name}  ({video.stat().st_size / 1e6:.0f} MB)\n{sep}")

    status["videos"][name] = {
        "status": "transcribing",
        "segments": [],
        "language": None,
        "duration": None,
        "elapsed": None,
    }
    save_status(status)

    txt_path = OUTPUT_DIR / f"{stem}.txt"
    srt_path = OUTPUT_DIR / f"{stem}.srt"
    t0 = time.time()

    segments, info = model.transcribe(
        str(video),
        beam_size=BEAM_SIZE,
        language=LANGUAGE,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    vid_status = status["videos"][name]
    vid_status["language"] = info.language
    vid_status["duration"] = round(info.duration, 1)
    print(f"  Language: {info.language} ({info.language_probability:.0%})  |  Duration: {info.duration:.1f}s\n")

    with open(txt_path, "w", encoding="utf-8") as tf, \
         open(srt_path, "w", encoding="utf-8") as sf:
        for i, seg in enumerate(segments, start=1):
            text = seg.text.strip()
            start_ts, end_ts = fmt_ts(seg.start), fmt_ts(seg.end)
            print(f"  [{start_ts} --> {end_ts}]  {text}")

            tf.write(text + "\n"); tf.flush()
            sf.write(f"{i}\n{start_ts} --> {end_ts}\n{text}\n\n"); sf.flush()

            vid_status["segments"].append({
                "id": i, "start": start_ts, "end": end_ts, "text": text
            })
            vid_status["elapsed"] = round(time.time() - t0, 1)
            save_status(status)

    elapsed = time.time() - t0
    speed = info.duration / elapsed if elapsed else 0
    vid_status["status"]  = "done"
    vid_status["elapsed"] = round(elapsed, 1)
    vid_status["speed"]   = f"{speed:.1f}x"
    vid_status["txt"]     = f"output/{stem}.txt"
    vid_status["srt"]     = f"output/{stem}.srt"
    save_status(status)
    print(f"\n  Done in {elapsed/60:.1f} min ({speed:.1f}x) -> output/{stem}.txt, output/{stem}.srt")


def main():
    videos = sorted(INPUT_DIR.glob("*.mp4"))
    if not videos:
        print("No .mp4 files found in input/ folder.")
        return

    status = {
        "state": "loading_model",
        "device": DEVICE,
        "model": MODEL_SIZE,
        "total_videos": len(videos),
        "video_list": [v.name for v in videos],
        "videos": {},
    }
    save_status(status)

    print(f"\n{'='*60}\n  Loading Whisper {MODEL_SIZE} on {DEVICE.upper()} ...\n{'='*60}")
    try:
        model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE,
                             download_root=str(CACHE_DIR))
        status["device"] = DEVICE
        print("  GPU loaded!")
    except Exception as e:
        print(f"  GPU failed: {e}\n  Falling back to CPU ...")
        model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8",
                             download_root=str(CACHE_DIR))
        status["device"] = "cpu"
        print("  CPU loaded!")

    status["state"] = "transcribing"
    save_status(status)

    total_t = time.time()
    for i, vid in enumerate(videos, 1):
        transcribe_video(model, vid, i, len(videos), status)

    status["state"] = "done"
    status["total_time"] = f"{(time.time()-total_t)/60:.1f} min"
    save_status(status)
    print(f"\n{'='*60}\n  All {len(videos)} videos done in {(time.time()-total_t)/60:.1f} min.\n{'='*60}\n")


if __name__ == "__main__":
    main()
