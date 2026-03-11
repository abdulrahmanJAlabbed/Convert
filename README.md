# Transcripe

Transcribes `.mp4` videos using **Whisper large-v3** with GPU.
Web dashboard with live progress, editing, and downloading.

## Structure

```
transcripe/
  input/              <- put .mp4 videos here
  output/
    txt/              <- Transcript_Week_1.txt, ...
    srt/              <- Transcript_Week_1.srt, ...
  app.py              <- all-in-one dashboard + transcription
  convert_pptx.py     <- PPTX to PDF converter
  requirements.txt
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Transcription Dashboard
```powershell
.venv\Scripts\activate
python app.py
# Open http://localhost:5000
# Click "Start Transcription" in the browser
```

### PPTX to PDF
```powershell
.venv\Scripts\activate
python convert_pptx.py myfile.pptx              # single file
python convert_pptx.py folder/                   # batch convert
```

> For best PPTX conversion, install [LibreOffice](https://www.libreoffice.org/download/) (free).
> Without it, a text-extraction fallback is used.
