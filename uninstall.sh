#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${HOME}/.claude/reflections"
CONFIG_FILE="${CONFIG_DIR}/config.json"

echo "Uninstalling claude-reflections..."

# Read container name from config
CONTAINER_NAME="claude-reflections-qdrant"
if [ -f "$CONFIG_FILE" ]; then
    CONTAINER_NAME=$(jq -r '.qdrant_container // "claude-reflections-qdrant"' "$CONFIG_FILE")
fi

# Remove Claude plugin
if command -v claude &> /dev/null; then
    echo "Removing Claude plugin..."
    claude plugin remove claude-reflections --scope user 2>/dev/null || true
fi

# Stop and remove Qdrant container
if command -v docker &> /dev/null; then
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Stopping Qdrant container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        echo "Removing Qdrant container..."
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
    else
        echo "Qdrant container '${CONTAINER_NAME}' not found."
    fi
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
echo "Note: The embedding model cache in ~/.cache/fastembed was not removed."
echo "To remove it manually: rm -rf ~/.cache/fastembed"
