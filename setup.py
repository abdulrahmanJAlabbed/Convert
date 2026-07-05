from setuptools import setup, find_packages

setup(
    name="transcripe",
    version="1.0.0",
    description="Award-Winning Universal Semantic File Converter",
    packages=find_packages(),
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.0.0",
        "faster-whisper>=1.0.0",
        "easyocr>=1.7.0",
        "Pillow>=10.0.0",
        "pypandoc>=1.13",
        "questionary>=2.0.0"
    ],
    entry_points={
        "console_scripts": [
            "transcripe=cli:app",
        ],
    },
)
