"""
Configuration Module
Centralized settings for the application.
"""

from pathlib import Path
import os

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


# Data paths
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"

# Output subdirectories
TRANSCRIPT_DIR = OUTPUT_DIR / "transcripts"
TXT_DIR = TRANSCRIPT_DIR / "txt"
SRT_DIR = TRANSCRIPT_DIR / "srt"
CONVERSION_DIR = OUTPUT_DIR / "conversions"
PDF_DIR = CONVERSION_DIR / "pdf"
IMG_DIR = CONVERSION_DIR / "images"
DOCS_DIR = CONVERSION_DIR / "docs"

# User-specific paths
USERS_DIR = PROJECT_ROOT / "users"
LECTURE_SLIDES_DIR = USERS_DIR / "lecture_slides"
MY_TRANSCRIPTS_DIR = USERS_DIR / "my_transcripts"

# Model cache
MODELS_DIR = PROJECT_ROOT / "models"

# Configuration
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "settings.json"

# Ensure all directories exist
for directory in [
    INPUT_DIR, OUTPUT_DIR, TRANSCRIPT_DIR, TXT_DIR, SRT_DIR,
    CONVERSION_DIR, PDF_DIR, IMG_DIR, DOCS_DIR,
    USERS_DIR, LECTURE_SLIDES_DIR, MY_TRANSCRIPTS_DIR,
    MODELS_DIR, CONFIG_DIR
]:
    directory.mkdir(parents=True, exist_ok=True)

# Set Hugging Face cache
os.environ["HF_HOME"] = str(MODELS_DIR)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Application settings
APP_CONFIG = {
    "host": "localhost",
    "port": 5000,
    "debug": os.getenv("DEBUG", "False") == "True",
    "max_upload_size": 2000,  # MB
    "supported_formats": {
        "audio": ["mp3", "wav", "m4a", "flac", "aac"],
        "video": ["mp4", "avi", "mov", "mkv", "flv"],
        "documents": ["pdf", "docx", "pptx", "xlsx"],
    },
}

# Transcription settings
TRANSCRIPTION_CONFIG = {
    "model_name": "Systran/faster-whisper-large-v3",
    "device": "cuda",
    "compute_type": "float16",
    "batch_size": 8,
}

# Conversion settings
CONVERSION_CONFIG = {
    "pptx_to_pdf": True,
    "pdf_extraction": True,
    "image_extraction": True,
}
