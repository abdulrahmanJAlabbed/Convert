# Video Transcription — Whisper large-v3

Batch-transcribes all `.mp4` files in this folder to `.txt` and `.srt` using
OpenAI's **Whisper large-v3**, the best free speech recognition model available.

## Requirements

- Python 3.10+
- NVIDIA GPU with updated driver (595+) — *required for GPU acceleration*
- No CUDA Toolkit installation needed — CUDA runtime is installed via pip

## Setup

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate it
.venv\Scripts\activate

# 3. Install dependencies (downloads ~1 GB of CUDA runtime + model)
pip install -r requirements.txt

# 4. Run transcription
python transcribe.py
```

## Output

For each `videoX.mp4` the script produces:
- `videoX.txt` — plain text transcript
- `videoX.srt` — subtitle file with timestamps

## Model Cache

The Whisper large-v3 model (~3 GB) is cached in `model_cache/` inside this folder.
You can delete it to free space — it will re-download on next run.

## Configuration

Edit the top of `transcribe.py` to change:
- `LANGUAGE` — force a language (e.g. `"en"`, `"ar"`) instead of auto-detect
- `BEAM_SIZE` — accuracy vs speed tradeoff (default: 5)
- `DEVICE` — `"cuda"` for GPU (default), `"cpu"` as fallback
