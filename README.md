# ⚡ Transcripe

**The Universal Semantic File Converter & Merger**

A powerful, interactive CLI tool that intelligently converts, merges, extracts, and transforms files using AI and specialized engines — all running 100% locally on your machine.

---

## ✨ Features

### 🎬 Video & 🎵 Audio
- **Transcribe** video/audio to text (`.txt`) or subtitles (`.srt`) using Whisper AI
- **Extract audio** from video (`.mp4` → `.mp3`, `.wav`, `.flac`)
- **Convert** between any media format (`.mkv` → `.mp4`, `.wav` → `.ogg`, etc.)
- **Video → GIF** with optimized 2-pass palette encoding
- **Compress** video with quality presets (high / medium / low)
- **Trim / Clip** video by start and end time
- **Extract frames** as PNG images at configurable FPS

### 📄 Documents
- **Convert** `.docx`, `.pptx`, `.odt`, `.epub`, `.rtf` → PDF, Markdown, HTML, DOCX, or plain text
- Powered by **LibreOffice** (PDF rendering) and **Pandoc** (format conversion)

### 📕 PDF
- **Extract text** from PDFs (no OCR needed for text-based PDFs)
- **Convert pages to images** (PNG) at high resolution
- **Split / extract pages** (e.g., pages 3-7 into a new PDF)
- Convert to Markdown, HTML, or DOCX

### 🖼️ Images
- **OCR** — extract text from images using EasyOCR AI
- **Convert** between formats (`.png`, `.jpg`, `.webp`, `.bmp`, `.tiff`, `.gif`)
- **Resize** by width/height with proportional scaling
- **Compress** with quality control (1–100)
- **Image → PDF**

### 📊 Data Transformation
- **CSV ↔ JSON** conversion
- **Excel → CSV** (multi-sheet aware)
- **CSV → Excel** (`.xlsx`)
- **YAML ↔ JSON**
- **JSON prettify / minify**

### 🔗 Merge
- **Text/Docs** — merge with customizable separators (horizontal lines, filename headers, numbered sections)
- **Images** — combine into PDF, stitch vertically, or create side-by-side collages
- **PDFs** — merge multiple PDFs into one
- **Audio/Video** — concatenate using FFmpeg

### 🤖 Interactive Agent UI
- Arrow-key navigable menus with beautiful theming
- **Native file browser** (Zenity on Linux, tkinter on Mac/Windows)
- **Drag & drop** file paths into the terminal
- **Turbo search** — find files by name across your entire home directory using C-optimized `find`
- Multi-file selection with running file list
- Step-by-step wizard workflow

---

## 📦 Installation

```bash
git clone https://github.com/abdulrahmanJAlabbed/Convert.git
cd Convert
./install.sh
```

The install script automatically:
1. Creates a Python virtual environment
2. Installs all dependencies
3. Installs `python3-tk` on Linux (for native file browser)
4. Creates a global `transcripe` command in `~/.local/bin`

### System Prerequisites
- **Python 3.10+**
- **FFmpeg** — for media conversion (`sudo apt install ffmpeg`)
- **LibreOffice** — for document → PDF (`sudo apt install libreoffice`)
- **Pandoc** — for document format conversion (`sudo apt install pandoc`)
- **Poppler** — for PDF → images (`sudo apt install poppler-utils`)

---

## 🚀 Usage

### Interactive Mode (recommended)
```bash
transcripe
```
The agent will guide you through file selection, format detection, and conversion.

### Direct Mode
```bash
transcripe video.mp4 --to mp3       # Extract audio
transcripe document.docx --to pdf   # Convert to PDF
transcripe data.csv --to json       # CSV to JSON
transcripe photo.png --to txt       # OCR text extraction
```

---

## 🏗️ Architecture

```
transcripe/
├── cli.py                 # Main CLI entry point (Typer + Questionary)
├── core/
│   └── dispatcher.py      # Smart file routing & interactive menus
├── engines/
│   ├── audio_video.py     # Whisper AI transcription + FFmpeg conversion
│   ├── documents.py       # LibreOffice + Pandoc + PDF tools
│   ├── images.py          # Pillow + EasyOCR
│   └── data.py            # Pandas data transformation
├── install.sh             # One-command installer
├── requirements.txt
└── setup.py
```

---

## 🔒 Privacy

Everything runs **100% locally** on your machine. No files are ever uploaded to any server.

---

## 📄 License

MIT
