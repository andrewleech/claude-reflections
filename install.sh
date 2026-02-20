#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${HOME}/.claude/reflections"
CONFIG_FILE="${CONFIG_DIR}/config.json"
MARKETPLACE_DIR="${HOME}/.claude/plugins/local-marketplace"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"

echo "Installing claude-reflections..."

# Check dependencies
if ! command -v uv &> /dev/null; then
    echo "Error: uv is required but not installed."
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Warning: jq not found. Install for better JSON handling."
fi

# Create config directory
mkdir -p "$CONFIG_DIR"

# Migration: detect old Qdrant-based config
if [ -f "$CONFIG_FILE" ] && grep -q '"qdrant_port"' "$CONFIG_FILE" 2>/dev/null; then
    echo ""
    echo "=== Migration from Qdrant to sqlite-vec ==="
    echo "Detected old Qdrant-based configuration."
    echo "Deleting state files to force full reindex on next search..."

    # Delete all state.json files (forces full reindex)
    find "$CONFIG_DIR" -name "state.json" -delete 2>/dev/null || true

    echo ""
    echo "If the old Qdrant container is still running, you can stop it manually:"
    echo "  docker stop claude-reflections-qdrant && docker rm claude-reflections-qdrant"
    echo ""
fi

# Write new config
cat > "$CONFIG_FILE" << 'EOF'
{
  "version": 2
}
EOF
echo "Config written to ${CONFIG_FILE}"

# Install Python dependencies and pre-download embedding model
echo "Setting up Python environment and downloading embedding model..."
cd "$SCRIPT_DIR"
uv sync

# Pre-download the embedding model by running a quick test
echo "Pre-downloading embedding model (this may take a moment)..."
uv run python -c "
from fastembed import TextEmbedding
print('Downloading embedding model...')
model = TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')
# Generate a test embedding to ensure model is fully loaded
list(model.embed(['test']))
print('Embedding model ready.')
"

# Set up local marketplace structure
echo "Setting up plugin marketplace..."
mkdir -p "${MARKETPLACE_DIR}/.claude-plugin"
mkdir -p "${MARKETPLACE_DIR}/plugins"

# Create marketplace manifest
cat > "${MARKETPLACE_DIR}/.claude-plugin/marketplace.json" << EOF
{
  "\$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "local",
  "description": "Local development plugins",
  "owner": {
    "name": "$(whoami)"
  },
  "plugins": [
    {
      "name": "claude-reflections",
      "description": "Minimal conversation memory with vector search",
      "version": "0.2.0",
      "author": {
        "name": "$(whoami)"
      },
      "source": "./plugins/claude-reflections",
      "category": "productivity"
    }
  ]
}
EOF

# Symlink plugin into marketplace
cd "${MARKETPLACE_DIR}/plugins"
ln -sf "$SCRIPT_DIR" claude-reflections
echo "Plugin symlinked to marketplace"

# Update Claude Code settings
echo "Updating Claude Code settings..."
mkdir -p "${HOME}/.claude"

if [ ! -f "$CLAUDE_SETTINGS" ]; then
    # Create new settings file
    cat > "$CLAUDE_SETTINGS" << 'EOF'
{
  "enabledPlugins": {
    "claude-reflections@local": true
  },
  "extraKnownMarketplaces": {
    "local": {
      "source": {
        "source": "directory",
        "path": "$MARKETPLACE_DIR"
      }
    }
  }
}
EOF
    # Replace $MARKETPLACE_DIR with actual path
    sed -i "s|\$MARKETPLACE_DIR|${MARKETPLACE_DIR}|g" "$CLAUDE_SETTINGS"
else
    # Merge with existing settings using jq if available, otherwise provide instructions
    if command -v jq &> /dev/null; then
        # Backup existing settings
        cp "$CLAUDE_SETTINGS" "${CLAUDE_SETTINGS}.backup"

        # Merge settings
        jq --arg mp_path "$MARKETPLACE_DIR" \
           '.enabledPlugins["claude-reflections@local"] = true |
            .extraKnownMarketplaces.local = {
              "source": {
                "source": "directory",
                "path": $mp_path
              }
            }' \
           "$CLAUDE_SETTINGS" > "${CLAUDE_SETTINGS}.tmp" && \
           mv "${CLAUDE_SETTINGS}.tmp" "$CLAUDE_SETTINGS"

        echo "Settings updated (backup saved to ${CLAUDE_SETTINGS}.backup)"
    else
        echo ""
        echo "WARNING: jq not installed, cannot automatically update settings."
        echo "Please manually add the following to ${CLAUDE_SETTINGS}:"
        echo ""
        echo '  "enabledPlugins": {'
        echo '    "claude-reflections@local": true'
        echo '  },'
        echo '  "extraKnownMarketplaces": {'
        echo '    "local": {'
        echo '      "source": {'
        echo '        "source": "directory",'
        echo "        \"path\": \"${MARKETPLACE_DIR}\""
        echo '      }'
        echo '    }'
        echo '  }'
        echo ""
    fi
fi

echo ""
echo "Installation complete!"
echo "  - Config: ${CONFIG_FILE}"
echo "  - Marketplace: ${MARKETPLACE_DIR}"
echo "  - Settings: ${CLAUDE_SETTINGS}"
echo "  - Vector databases are created per-project on first use"
echo ""
echo "NEXT STEPS:"
echo "  1. Restart Claude Code to load the plugin and skill"
echo "  2. Verify installation:"
echo "     - Ask: 'What skills are available?' → should show 'reflections'"
echo "     - Ask: 'What plugins are installed?' → should show 'claude-reflections'"
echo "  3. Try asking: 'How did we implement X?' to trigger the skill"
echo ""
echo "The skill searches past conversations using CLI commands."
echo "Search automatically indexes before searching (incremental)."
echo "Use 'uv run claude-reflections status' to check indexing status."
