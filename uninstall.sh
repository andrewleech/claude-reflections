#!/bin/bash
set -e

CONFIG_DIR="${HOME}/.claude/reflections"

echo "Uninstalling claude-reflections..."

# Remove plugin symlink from local marketplace
MARKETPLACE_DIR="${HOME}/.claude/plugins/local-marketplace"
if [ -L "${MARKETPLACE_DIR}/plugins/claude-reflections" ]; then
    echo "Removing plugin symlink from marketplace..."
    rm "${MARKETPLACE_DIR}/plugins/claude-reflections"
    echo "Plugin removed from marketplace."
fi

# Ask about data removal
echo ""
read -p "Remove stored data and config in ${CONFIG_DIR}? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing data directory..."
    rm -rf "$CONFIG_DIR"
    echo "Data removed."
else
    echo "Data preserved at ${CONFIG_DIR}"
fi

echo ""
echo "Uninstall complete."
echo ""
echo "To complete removal:"
echo "  1. Restart Claude Code to unload the plugin"
echo "  2. Optionally remove embedding model cache: rm -rf ~/.cache/fastembed"
echo "  3. Optionally clean marketplace entry from ~/.claude/settings.json"
