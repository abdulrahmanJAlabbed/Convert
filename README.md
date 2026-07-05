# ⚡ Transcripe

**The Universal Semantic File Converter, Merger & Transcriber — 100% local.**

Transcripe is an interactive command‑line tool that converts, merges, extracts, and
transcribes almost any file — video, audio, documents, PDFs, images, and data — using
AI (Whisper, EasyOCR) and best‑in‑class engines (FFmpeg, LibreOffice, Pandoc, Poppler).
Everything runs on **your machine**. No uploads, no cloud, no tracking.

```
████████╗██████╗  █████╗ ███╗   ██╗███████╗ ██████╗██████╗ ██╗██████╗ ███████╗
╚══██╔══╝██╔══██╗██╔══██╗████╗  ██║██╔════╝██╔════╝██╔══██╗██║██╔══██╗██╔════╝
   ██║   ██████╔╝███████║██╔██╗ ██║███████╗██║     ██████╔╝██║██████╔╝█████╗
   ██║   ██╔══██╗██╔══██║██║╚██╗██║╚════██║██║     ██╔══██╗██║██╔═══╝ ██╔══╝
   ██║   ██║  ██║██║  ██║██║ ╚████║███████║╚██████╗██║  ██║██║██║     ███████╗
   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚══════╝
```

---

## ✨ Features

### 🎬 Video & 🎵 Audio
- **Transcribe** to text (`.txt`) or subtitles (`.srt`) with **Whisper** (GPU‑accelerated when available)
- **Extract audio** from video (`.mp4` → `.mp3` / `.wav` / `.flac`)
- **Convert** between any media format (`.mkv` → `.mp4`, `.wav` → `.ogg`, …)
- **Video → GIF** (optimized two‑pass palette encoding)
- **Compress** video (high / medium / low presets)
- **Trim / clip** by start–end time
- **Extract frames** as PNG images at a chosen FPS

### 📄 Documents
- Convert `.docx`, `.pptx`, `.ppt`, `.odt`, `.epub`, `.rtf` → **PDF** (auto‑picks MS Office for high fidelity when installed, else LibreOffice)
- Convert `.docx` / `.pptx` → **Markdown / HTML / plain text** (Pandoc)

### 📕 PDF
- **Extract text** (no OCR needed for text‑based PDFs)
- **OCR** scanned / image‑based PDFs → text (renders pages, then reads with AI)
- **Pages → images** (PNG) at high resolution
- **Split / extract pages** (e.g. `3-7` or `1,4,9-12`)
- Convert to **Markdown / HTML / Word** (text is extracted first, then rendered)

### 🖼️ Images
- **OCR** — extract text with **RapidOCR** (fast, accurate, multilingual) and an **EasyOCR** fallback for extra scripts
- **Multi‑language OCR** — auto (Latin + Türkçe + numbers) or pick English / Turkish / Arabic / Chinese / custom codes
- **Convert** between `.png`, `.jpg`, `.webp`, `.bmp`, `.tiff`, `.gif`
- **Resize** (proportional or exact) and **compress** (quality control)
- **Image → PDF**

### 📊 Data
- **CSV ↔ JSON**, **CSV → Excel**, **Excel → CSV / JSON** (multi‑sheet aware)
- **YAML ↔ JSON**, **XML → JSON**, JSON **prettify / minify**

### 🔗 Merge
- **Text/Docs** — merge with separators (rules, filename headers, numbered sections); PDFs & DOCX are text‑extracted automatically
- **Images** — combine into a PDF, stitch vertically, or side‑by‑side collage
- **PDFs** — merge many into one
- **Audio/Video** — concatenate with FFmpeg

### 🤖 Smart interactive agent
- Big animated banner + themed, arrow‑key menus (Rich + Questionary + pyfiglet)
- **Auto‑detects** each file's type and **recommends** the best action
- **Shows where output will be saved** and lets you change it (with overwrite protection)
- **Batch mode** — convert many files at once, optionally into a single folder
- **Parallel processing** for subprocess conversions (≈**3× faster** batches)
- Native file browser (Zenity on Linux, tkinter on macOS/Windows), drag‑and‑drop, and turbo filename search
- Offers to open the output folder when finished

---

## 📦 Installation

### Linux / macOS (one command)
```bash
git clone https://github.com/abdulrahmanJAlabbed/Convert.git transcripe
cd transcripe
./install.sh
```
`install.sh` auto‑detects your package manager (apt / dnf / pacman / Homebrew), installs the
system tools, creates a virtualenv, installs Python deps, and adds a global `transcripe` command.

### Windows
```powershell
git clone https://github.com/abdulrahmanJAlabbed/Convert.git transcripe
cd transcripe
python -m venv venv
venv\Scripts\pip install -r requirements.txt -e .
venv\Scripts\python cli.py
```
Then install the system tools (see below) and make sure they're on your `PATH`.

### System prerequisites

| Tool         | Used for                     | Linux (apt)             | macOS (brew)              | Windows            |
|--------------|------------------------------|-------------------------|---------------------------|--------------------|
| **Python 3.10+** | everything               | `python3`               | `python`                  | python.org         |
| **FFmpeg**   | audio/video                  | `ffmpeg`                | `ffmpeg`                  | choco / gyan.dev   |
| **LibreOffice** | documents → PDF           | `libreoffice`           | `--cask libreoffice`      | libreoffice.org    |
| **Poppler**  | PDF → images                 | `poppler-utils`         | `poppler`                 | conda / release    |
| **Pandoc**   | document formats             | `pandoc`                | `pandoc`                  | choco / pandoc.org |

> Pandoc can also self‑install: `python -c "import pypandoc; pypandoc.download_pandoc()"`.
> Whisper and EasyOCR models download automatically on first use into `model_cache/`.
> **Optional (Windows/macOS):** `pip install docx2pdf` + MS Office enables the high‑fidelity
> Office backend for `.docx`/`.pptx`; Transcripe auto‑detects it and falls back to LibreOffice otherwise.

---

## 🚀 Usage

### Interactive mode (recommended)
```bash
transcripe
```
The agent guides you through file selection → detected type → recommended action → output location.

### Direct mode
```bash
transcripe lecture.mp4 --to srt      # transcribe to subtitles
transcripe slides.pptx --to pdf      # PowerPoint → PDF
transcripe report.docx --to md       # Word → Markdown
transcripe data.csv   --to json      # CSV → JSON
transcripe scan.png   --to txt       # OCR
```

### Check your machine & verify quality
```bash
transcripe --doctor        # environment + capability report
transcripe --self-test     # run one real conversion per feature, show pass/fail
transcripe --self-test --slow   # also exercise the transcription pipeline
```

---

## ⚙️ Configuration (environment variables)

| Variable                 | Default            | Description                                        |
|--------------------------|--------------------|----------------------------------------------------|
| `TRANSCRIPE_MODEL`       | `large-v3`         | Whisper model (`tiny`,`base`,`small`,`medium`,`large-v3`) |
| `TRANSCRIPE_DEVICE`      | auto (`cuda`/`cpu`)| Force transcription device                          |
| `TRANSCRIPE_COMPUTE`     | `float16`/`int8`   | Compute type (GPU/CPU)                              |
| `TRANSCRIPE_BEAM`        | `5`                | Whisper beam size                                   |
| `TRANSCRIPE_WORKERS`     | `min(4, CPUs)`     | Parallel workers for batch conversions             |
| `TRANSCRIPE_DOC_BACKEND` | auto               | Force document→PDF backend (`libreoffice` / `msoffice`) |

Example — fast CPU transcription:
```bash
TRANSCRIPE_MODEL=small TRANSCRIPE_DEVICE=cpu transcripe lecture.mp4 --to txt
```

---

## 🧪 Testing

Transcripe ships a self-testing architecture so you always know *exactly* which
conversion works on a given machine:

- **`core/capabilities.py`** probes every dependency (FFmpeg, LibreOffice, MS Office,
  Poppler, Pandoc, RapidOCR/EasyOCR, Whisper, GPU…) and gates features accordingly.
- **`core/selftest.py`** generates synthetic fixtures and runs one real conversion
  per feature, returning a pass/fail/skip matrix.
- **`transcripe --self-test`** prints that matrix; missing‑dependency conversions
  are *skipped* (not failed), so the tool adapts to any environment.

Run the developer test suite with pytest (each conversion is an individual test,
and round‑trip data‑integrity checks guard import/export quality):
```bash
pip install -r requirements-dev.txt
pytest            # skips conversions whose tools aren't installed
pytest --slow     # include the transcription pipeline
```

---

## ⚡ Performance

- **Instant startup** — heavy ML libraries load lazily (≈0.1 s to first menu).
- **GPU auto‑detect** — Whisper uses CUDA when available, else CPU (verified ~6× real‑time on GPU).
- **Model caching** — the Whisper model loads once and is reused across a batch.
- **Parallel batches** — independent conversions run concurrently (measured **2.8×** on LibreOffice PPTX→PDF). Transcription/OCR stay sequential for stability.
- **Document fidelity** — auto‑selects MS Office for `.docx/.pptx` when installed (Windows/macOS), else LibreOffice; MS Office failures self‑heal to LibreOffice.

---

## 🏗️ Architecture

```
transcripe/
├── cli.py                 # Typer entry point, banner, interactive wizard, --doctor/--self-test
├── core/
│   ├── dispatcher.py      # File routing, batch/parallel engine, merge logic, capability guards
│   ├── capabilities.py    # Environment detection + feature gating (adapts to any system)
│   ├── selftest.py        # Fixture generation + per-conversion smoke tests
│   └── doctor.py          # `--doctor` / `--self-test` reports
├── engines/
│   ├── audio_video.py     # Whisper transcription + FFmpeg (convert/gif/compress/trim/frames)
│   ├── documents.py       # LibreOffice + Pandoc + pypdf + pdf2image (+ scanned‑PDF OCR)
│   ├── images.py          # Pillow image ops + OCR
│   ├── ocr.py             # Unified OCR: RapidOCR (default) + EasyOCR fallback, multilingual
│   └── data.py            # pandas / PyYAML / xml transforms
├── install.sh             # Cross‑platform installer
├── requirements.txt
└── setup.py
```

---

## ⚠️ Known limitations

- **OCR** uses RapidOCR by default (great for Latin scripts + Turkish + numbers); for Arabic / Chinese / Cyrillic / Indic it automatically switches to EasyOCR language packs. Very low‑quality photos may still drop spaces in dense lines.
- System tools (FFmpeg / LibreOffice / Poppler) must be installed separately on macOS/Windows.
- The code paths are written cross‑platform (macOS/Windows branches for the file browser, folder‑open, and search), but the maintainers primarily test on Linux.

---

## 🔒 Privacy

Everything runs **100% locally**. Your files never leave your machine.

## 📄 License

MIT
