# Setup Instructions

## Prerequisites
- Python 3.8+
- CUDA 12.x (for GPU acceleration) - Optional but recommended
- LibreOffice (for PPTX conversion) - Optional

## Installation

### 1. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Environment Variables
```bash
cp .env.example .env
# Edit .env if needed
```

### 4. Install Optional Dependencies
```bash
# For PPTX conversion with full fidelity
# Windows
# Download from https://www.libreoffice.org/download/

# Ubuntu/Debian
sudo apt-get install libreoffice

# macOS
brew install libreoffice
```

## Directory Structure

After setup, your directory structure should look like:
```
transcripe/
├── src/              # Application code
├── data/
│   ├── input/       # Add files here for processing
│   └── output/      # Results will appear here
├── users/
│   ├── lecture_slides/
│   └── my_transcripts/
├── models/          # ML models cache (auto-downloaded)
└── config/          # Settings
```

## Running the Application

### Start the Dashboard
```bash
python app.py
```

Then open: http://localhost:5000

### Batch Process Videos (Manual)
```bash
python manual_run.py
```

### Convert PPTX Files
```bash
python convert_pptx.py <file-or-folder>
```

## Usage

### Transcription
1. Place `.mp4` files in `data/input/videos/`
2. Open dashboard: http://localhost:5000
3. Click "Start Transcription"
4. Results appear in:
   - Text: `users/my_transcripts/*.txt`
   - Subtitles: `users/my_transcripts/*.srt`

### Slide Conversion
1. Place `.pptx` files in `data/input/slides/` or `users/lecture_slides/`
2. Run: `python convert_pptx.py`
3. PDFs appear in `data/output/conversions/pdf/`
4. Images appear in `data/output/conversions/images/`

## Troubleshooting

### CUDA Not Available
```bash
# Check CUDA installation
python -c "import torch; print(torch.cuda.is_available())"

# If False, install CPU version or CUDA drivers
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Out of Memory
Reduce batch size in `config/settings.json`:
```json
{
  "transcription": {
    "batch_size": 4
  }
}
```

### Missing Dependencies
```bash
pip install --upgrade -r requirements.txt
```

## Next Steps

- Read [STRUCTURE.md](STRUCTURE.md) for directory organization
- Review [API.md](API.md) for available endpoints
- Check configuration in `config/settings.json`
