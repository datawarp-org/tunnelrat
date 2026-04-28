#!/usr/bin/env bash
# install.sh — Install TunnelRAT dependencies and create a launcher
set -e

INSTALL_DIR="$HOME/.local/share/tunnelrat"
BIN="$HOME/.local/bin/tunnelrat"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing system packages (requires sudo)..."
sudo dnf install -y python3-pip python3-PyQt6 python3-pyqt6-webengine || true

echo "==> Installing Python dependencies..."
pip3 install --user -r "$SCRIPT_DIR/requirements.txt"

echo "==> Copying application files..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/icons"
cp -r "$SCRIPT_DIR/"*.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/tunnelrat.png" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/tunnelrat.ico" "$INSTALL_DIR/" 2>/dev/null || true
[ -d "$SCRIPT_DIR/icons" ] && cp "$SCRIPT_DIR/icons/"* "$INSTALL_DIR/icons/" 2>/dev/null || true

echo "==> Creating launcher at $BIN..."
mkdir -p "$HOME/.local/bin"
cat > "$BIN" <<'EOF'
#!/usr/bin/env bash
# TunnelRAT launcher
export QT_QPA_PLATFORM=xcb
exec python3 "$HOME/.local/share/tunnelrat/tunnelrat.py" "$@"
EOF
chmod +x "$BIN"

echo "==> Installing icons..."
for size in 256 128 64 48 32 16; do
    mkdir -p "$HOME/.local/share/icons/hicolor/${size}x${size}/apps"
    if [ -f "$SCRIPT_DIR/icons/tunnelrat_${size}.png" ]; then
        cp "$SCRIPT_DIR/icons/tunnelrat_${size}.png" \
           "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/tunnelrat.png"
    fi
done
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "==> Creating .desktop file..."
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/tunnelrat.desktop" <<EOF
[Desktop Entry]
Name=TunnelRAT
Comment=TunnelRAT — SSH session manager for Linux
Exec=$BIN
Icon=$HOME/.local/share/tunnelrat/icons/tunnelrat_256.png
Terminal=false
Type=Application
Categories=Network;RemoteAccess;
Keywords=ssh;terminal;server;remote;
StartupWMClass=tunnelrat
EOF

echo ""
echo "✓ Installation complete!"
echo ""
echo "  Run with:  tunnelrat"
echo "  (Make sure ~/.local/bin is in your PATH)"
echo ""
echo "  If PATH is not set, add this to ~/.bashrc or ~/.bash_profile:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "  On first run, use File → Import Sessions to load a SuperPutty Sessions.XML"
