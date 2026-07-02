from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from engines import audio_video, documents, images

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".mpeg", ".mpg", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
DOC_EXTS = {".pptx", ".ppt", ".docx", ".doc", ".epub", ".odt", ".rtf", ".txt", ".md", ".csv", ".xls", ".xlsx", ".ods"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".bmp", ".tiff", ".gif", ".ico", ".svg"}

def dispatch_conversion(input_path: Path, target_format: str | None, console: Console):
    if not input_path.exists():
        raise FileNotFoundError(f"Cannot find {input_path}")
        
    ext = input_path.suffix.lower()
    
    # INTERACTIVE MODE
    if target_format is None:
        if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
            console.print("\n[yellow]Video/Audio File Detected.[/yellow]")
            console.print("1. Transcription (.txt)")
            console.print("2. Subtitles (.srt)")
            choice = Prompt.ask("What would you like to generate?", choices=["1", "2"], default="1")
            
            target_format = "txt" if choice == "1" else "srt"
        
        elif ext in DOC_EXTS:
            console.print("\n[yellow]Document File Detected.[/yellow]")
            console.print("1. PDF Document (.pdf)")
            console.print("2. Markdown Document (.md)")
            choice = Prompt.ask("What would you like to generate?", choices=["1", "2"], default="1")
            target_format = "pdf" if choice == "1" else "md"
            
        elif ext in IMAGE_EXTS:
            console.print("\n[yellow]Image File Detected.[/yellow]")
            console.print("1. Extract Text (OCR -> .txt)")
            console.print("2. Convert Format (e.g. to .webp, .png)")
            choice = Prompt.ask("What would you like to do?", choices=["1", "2"], default="1")
            
            if choice == "1":
                target_format = "txt"
            else:
                target_format = Prompt.ask("Enter target extension (png, jpg, webp)", default="webp")
        
        else:
            raise ValueError(f"No interactive options defined yet for {ext}. Please use --to flag.")
            
    # DIRECTED MODE
    target_format = target_format.lower().strip(".")
    
    # Route to appropriate engine
    if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
        if target_format in ["txt", "srt"]:
            audio_video.transcribe(input_path, target_format, console)
        else:
            raise ValueError(f"Cannot convert video/audio to {target_format} yet.")
            
    elif ext in DOC_EXTS:
        if target_format == "pdf":
            documents.convert_document_to_pdf_engine(input_path, console)
        elif target_format == "md":
            documents.convert_with_pandoc(input_path, target_format, console)
        else:
            raise ValueError(f"Cannot convert {ext} to {target_format} yet.")
            
    elif ext in IMAGE_EXTS:
        images.convert_image(input_path, target_format, console)
        
    else:
        raise ValueError(f"Unsupported input format: {ext}")
