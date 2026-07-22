from setuptools import setup, find_packages

setup(
    name="transcripe",
    version="1.0.0",
    description="Award-Winning Universal Semantic File Converter",
    packages=find_packages(),
    py_modules=["cli", "commands"],  # top-level modules; find_packages() misses them
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "faster-whisper>=1.0.0",
        "rapidocr-onnxruntime>=1.3.0",
        "onnxruntime>=1.16.0",
        "easyocr>=1.7.0",
        "Pillow>=10.0.0",
        "pypandoc>=1.13",
        "questionary>=2.0.0",
        "pyfiglet>=1.0.0",
        "pypdf>=4.0.0",
        "pdf2image>=1.16.0",
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "pyyaml>=6.0.0",
        "charset-normalizer>=3.0.0",
        "py7zr>=0.20.0",
        "rarfile>=4.0",
        "trimesh>=4.0.0",
        "pillow-heif>=0.16.0",
        "PyMuPDF>=1.24.0",
        "pdf2docx>=0.5.8",
        "ocrmypdf>=16.0.0"
    ],
    entry_points={
        "console_scripts": [
            "transcripe=cli:main_entry",
        ],
    },
)
