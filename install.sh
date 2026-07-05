#!/bin/bash
set -e

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Installing Transcripe..."

# ── 0. Install system dependencies (best-effort, per platform) ──────────────
# Needed binaries: ffmpeg (media), libreoffice (docs→pdf), poppler (pdf→images),
# pandoc (doc formats — can also self-download), tk (native file browser).
install_system_deps() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "🐧 Debian/Ubuntu detected — installing system dependencies (sudo)..."
        sudo apt-get update -qq
        sudo apt-get install -y ffmpeg libreoffice poppler-utils pandoc python3-tk || true
    elif command -v dnf >/dev/null 2>&1; then
        echo "🐧 Fedora detected — installing system dependencies (sudo)..."
        sudo dnf install -y ffmpeg libreoffice poppler-utils pandoc python3-tkinter || true
    elif command -v pacman >/dev/null 2>&1; then
        echo "🐧 Arch detected — installing system dependencies (sudo)..."
        sudo pacman -Sy --noconfirm ffmpeg libreoffice-fresh poppler pandoc tk || true
    elif command -v brew >/dev/null 2>&1; then
        echo "🍏 macOS (Homebrew) detected — installing system dependencies..."
        brew install ffmpeg poppler pandoc python-tk || true
        brew install --cask libreoffice || true
    else
        echo "⚠️  Could not detect a package manager."
        echo "   Please install manually: ffmpeg, libreoffice, poppler, pandoc, tk."
    fi
}
install_system_deps

# ── 1. Ensure virtual environment exists ────────────────────────────────────
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# ── 2. Install Python requirements ──────────────────────────────────────────
echo "📥 Installing Python dependencies (this might take a minute)..."
"$PROJECT_DIR/venv/bin/pip" install -q --upgrade pip
"$PROJECT_DIR/venv/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"
"$PROJECT_DIR/venv/bin/pip" install -q -e "$PROJECT_DIR"

# ── 3. Create the executable wrapper in ~/.local/bin ────────────────────────
mkdir -p "$HOME/.local/bin"
BIN_PATH="$HOME/.local/bin/transcripe"

# Unquoted heredoc expands $PROJECT_DIR now; \$@ stays literal (portable, no sed).
cat > "$BIN_PATH" <<EOF
#!/bin/bash
"$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/cli.py" "\$@"
EOF
chmod +x "$BIN_PATH"

echo ""
echo "✅ Installation complete!"
echo "🎉 Run it from anywhere by typing: transcripe"
echo "   If 'transcripe' is not found, add ~/.local/bin to your PATH:"
echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
