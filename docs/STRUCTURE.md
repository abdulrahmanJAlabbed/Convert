# Project Structure

## Overview

Transcripe is organized into a scalable, modular structure designed to support multi-format conversion services.

```
transcripe/
├── src/                          # Application source code
│   ├── __init__.py
│   ├── config.py                 # Centralized configuration
│   ├── api/                      # Flask routes and endpoints
│   ├── services/                 # Business logic (transcription, conversion, etc.)
│   └── utils/                    # Helper functions and utilities
│
├── data/                         # Processing data (gitignored)
│   ├── input/                    # Raw files to process
│   │   ├── videos/              # Video files for transcription
│   │   ├── slides/              # Presentation files for conversion
│   │   └── documents/           # Documents for conversion
│   └── output/                   # Generated outputs (organized by type)
│       ├── transcripts/
│       │   ├── txt/             # Text transcripts
│       │   └── srt/             # Subtitle files
│       └── conversions/
│           ├── pdf/             # Converted PDFs
│           ├── images/          # Extracted images
│           └── docs/            # Document conversions
│
├── users/                        # User-specific content (gitignored)
│   ├── lecture_slides/          # Lecture presentations and study materials
│   └── my_transcripts/          # Personal transcription outputs
│
├── models/                       # ML model cache (gitignored)
│   └── [Hugging Face model cache]
│
├── config/                       # Configuration files
│   └── settings.json            # Application settings
│
├── docs/                         # Documentation
│   ├── STRUCTURE.md             # This file
│   ├── API.md                   # API documentation
│   └── SETUP.md                 # Setup instructions
│
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── app.py                        # Main Flask application (to be refactored)
├── convert_pptx.py              # PPTX converter (to be moved to services)
├── manual_run.py                # Manual execution script
└── README.md                     # Project README
```

## Directory Purposes

### `src/` - Source Code
Contains all application logic, organized by function:
- **config.py**: Centralized configuration and path management
- **api/**: Flask routes and HTTP handlers
- **services/**: Core business logic (transcription, conversions, file processing)
- **utils/**: Reusable helper functions

### `data/` - Processing Data
Temporary storage for files being processed:
- **input/**: Raw files awaiting processing
- **output/**: Processed results organized by output type

### `users/` - User Content
Persistent user files and outputs:
- **my_transcripts/**: Personal transcription outputs
- **lecture_slides/**: Lecture materials and slides

### `models/` - Model Cache
Hugging Face model cache for ML models (large files, typically excluded from git)

### `config/` - Configuration
Application settings and configuration files (can be environment-specific)

### `docs/` - Documentation
Project documentation including setup, API reference, and architecture

## Next Steps

1. **Refactor app.py**: Extract routes to `src/api/routes.py`
2. **Modularize services**: Create `src/services/transcriber.py`, `src/services/converter.py`
3. **Create utilities**: Add helper functions to `src/utils/`
4. **Update imports**: Update all imports to use new structure
5. **Add tests**: Create test directory with unit tests
6. **gitignore**: Add directories to `.gitignore` (data/, models/, users/, __pycache__)

## Usage

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python app.py

# Access
http://localhost:5000
```
