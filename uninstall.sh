#!/usr/bin/env bash
# uninstall.sh — Remove TunnelRAT from this user account
set -e

echo "==> Removing TunnelRAT..."

rm -f  "$HOME/.local/bin/tunnelrat"
rm -rf "$HOME/.local/share/tunnelrat"
rm -f  "$HOME/.local/share/applications/tunnelrat.desktop"

echo "✓ TunnelRAT removed."
echo ""
echo "  Your sessions are kept at: ~/.config/tunnelrat/sessions.json"
echo "  To also delete sessions:   rm -rf ~/.config/tunnelrat"
