#!/bin/bash

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Installing Transcripe..."

# 0. Install system dependencies if on Debian/Ubuntu Linux (python3-tk for the native browser)
if command -v apt-get &> /dev/null; then
    echo "🐧 Linux detected. Checking system dependencies..."
    if ! dpkg -l | grep -q "python3-tk"; then
        echo "🪟 Installing 'python3-tk' for the native file browser (Requires sudo)..."
        sudo apt-get update -qq
        sudo apt-get install -y python3-tk
    fi
fi

# 1. Ensure virtual environment exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv"
fi

# 2. Install requirements in the virtual environment
echo "📥 Installing dependencies (this might take a minute)..."
"$PROJECT_DIR/venv/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt"
"$PROJECT_DIR/venv/bin/pip" install -q -e "$PROJECT_DIR"

# 3. Create the executable wrapper in ~/.local/bin
mkdir -p "$HOME/.local/bin"
BIN_PATH="$HOME/.local/bin/transcripe"

cat << 'EOF' > "$BIN_PATH"
#!/bin/bash
PROJECT_DIR="TARGET_DIR"
"$PROJECT_DIR/venv/bin/python" "$PROJECT_DIR/cli.py" "$@"
EOF

# Replace TARGET_DIR with actual path
sed -i "s|TARGET_DIR|$PROJECT_DIR|g" "$BIN_PATH"
chmod +x "$BIN_PATH"

echo "✅ Installation complete!"
echo ""
echo "🎉 You can now use the tool from anywhere by typing: transcripe"
echo "Note: If 'transcripe' is not found, you may need to restart your terminal or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
