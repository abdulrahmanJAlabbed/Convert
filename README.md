# Video Transcription (Whisper large-v3 + GPU)

Transcribes `.mp4` videos using **OpenAI Whisper large-v3** with GPU acceleration.
Includes a **live web dashboard** to monitor progress.

## Project Structure

```
transcripe/
  input/           <- put your .mp4 videos here
  output/          <- transcripts appear here (.txt + .srt)
  transcribe.py    <- runs the transcription
  dashboard.py     <- live web dashboard
  requirements.txt
  .gitignore
```

## Setup (run in PowerShell)

```powershell
# 1. Create & activate venv
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies (~600 MB CUDA libs)
pip install -r requirements.txt
```

## Usage

```powershell
# Terminal 1 — dashboard
.venv\Scripts\activate
python dashboard.py

# Terminal 2 — transcription
.venv\Scripts\activate
python transcribe.py
```

Open **http://localhost:5000** to see the dashboard.

## Configuration

Edit the top of `transcribe.py`:

| Setting    | Default  | Description                          |
|------------|----------|--------------------------------------|
| `LANGUAGE` | `None`   | Auto-detect. Force: `"en"`, `"ar"`   |
| `BEAM_SIZE`| `5`      | Higher = more accurate, slower       |
| `DEVICE`   | `"cuda"` | `"cpu"` to skip GPU                  |

## Cleanup

- `model_cache/` — delete to free ~3 GB (re-downloads on next run)
- `.venv/` — delete to remove all packages
- `output/` — delete to clear transcripts
