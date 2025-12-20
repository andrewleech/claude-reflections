#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="${HOME}/.claude/reflections"
CONFIG_FILE="${CONFIG_DIR}/config.json"
CONTAINER_NAME="claude-reflections-qdrant"

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

if ! command -v claude &> /dev/null; then
    echo "Error: claude CLI is required but not installed."
    exit 1
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

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Qdrant container '${CONTAINER_NAME}' already exists."
    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Container is running."
        # Read existing config
        if [ -f "$CONFIG_FILE" ]; then
            QDRANT_PORT=$(jq -r '.qdrant_port' "$CONFIG_FILE")
            echo "Using existing Qdrant on port ${QDRANT_PORT}"
        fi
    else
        echo "Starting existing container..."
        docker start "$CONTAINER_NAME"
        if [ -f "$CONFIG_FILE" ]; then
            QDRANT_PORT=$(jq -r '.qdrant_port' "$CONFIG_FILE")
        fi
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
        qdrant/qdrant

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

# Create config directory
mkdir -p "$CONFIG_DIR"

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

# Install as Claude plugin system-wide
echo "Installing Claude plugin..."
claude plugin add "$SCRIPT_DIR" --scope user

echo ""
echo "Installation complete!"
echo "  - Qdrant running on port ${QDRANT_PORT}"
echo "  - Config: ${CONFIG_FILE}"
echo "  - Plugin installed system-wide"
echo ""
echo "The plugin will automatically index conversations on session end."
echo "Use 'claude-reflections status' to check indexing status."
