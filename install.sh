#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${HOME}/.claude/reflections"
CONFIG_FILE="${CONFIG_DIR}/config.json"
CONTAINER_NAME="claude-reflections-qdrant"
MARKETPLACE_DIR="${HOME}/.claude/plugins/local-marketplace"
CLAUDE_SETTINGS="${HOME}/.claude/settings.json"

echo "Installing claude-reflections..."

# Check dependencies
if ! command -v docker &> /dev/null; then
    echo "Error: docker is required but not installed."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "Error: uv is required but not installed."
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "Warning: jq not found. Install for better JSON handling."
fi

# Find a free port in range 16333-26333
find_free_port() {
    local port
    for port in $(shuf -i 16333-26333 -n 100); do
        if ! ss -tuln | grep -q ":${port} "; then
            echo "$port"
            return 0
        fi
    done
    echo "Error: Could not find a free port" >&2
    return 1
}

# Create config directory early (before Docker volume mount to avoid root ownership)
mkdir -p "$CONFIG_DIR"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Qdrant container '${CONTAINER_NAME}' already exists."
    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Container is running."
        # Read existing config
        if [ -f "$CONFIG_FILE" ]; then
            QDRANT_PORT=$(jq -r '.qdrant_port' "$CONFIG_FILE" 2>/dev/null || grep -o '"qdrant_port":[^,}]*' "$CONFIG_FILE" | cut -d: -f2 | tr -d ' ')
            echo "Using existing Qdrant on port ${QDRANT_PORT}"
        fi
    else
        echo "Starting existing container..."
        docker start "$CONTAINER_NAME"
        if [ -f "$CONFIG_FILE" ]; then
            QDRANT_PORT=$(jq -r '.qdrant_port' "$CONFIG_FILE" 2>/dev/null || grep -o '"qdrant_port":[^,}]*' "$CONFIG_FILE" | cut -d: -f2 | tr -d ' ')
        fi
    fi
    # Fallback: if config file missing but container exists, get port from Docker
    if [ -z "$QDRANT_PORT" ]; then
        QDRANT_PORT=$(docker port "$CONTAINER_NAME" 6333 2>/dev/null | cut -d: -f2)
        echo "Retrieved port ${QDRANT_PORT} from Docker"
    fi
else
    # Find a free port and start new container
    QDRANT_PORT=$(find_free_port)
    echo "Starting Qdrant on port ${QDRANT_PORT}..."

    docker run -d \
        --name "$CONTAINER_NAME" \
        --restart unless-stopped \
        -p "${QDRANT_PORT}:6333" \
        -v "${CONFIG_DIR}/qdrant_storage:/qdrant/storage" \
        qdrant/qdrant:v1.16

    # Wait for Qdrant to be ready
    echo "Waiting for Qdrant to start..."
    for i in {1..30}; do
        if curl -s "http://localhost:${QDRANT_PORT}/healthz" > /dev/null 2>&1; then
            echo "Qdrant is ready."
            break
        fi
        sleep 1
    done
fi

# Write config file
cat > "$CONFIG_FILE" << EOF
{
  "qdrant_port": ${QDRANT_PORT},
  "qdrant_host": "localhost",
  "qdrant_container": "${CONTAINER_NAME}"
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
echo "  - Qdrant running on port ${QDRANT_PORT}"
echo "  - Config: ${CONFIG_FILE}"
echo "  - Marketplace: ${MARKETPLACE_DIR}"
echo "  - Settings: ${CLAUDE_SETTINGS}"
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
