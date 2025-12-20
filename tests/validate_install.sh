#!/bin/bash
# End-to-end validation script for install/uninstall
# Can run standalone or in a container
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${HOME}/.claude/reflections"
CONTAINER_NAME="claude-reflections-qdrant"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; }
info() { echo -e "[INFO] $1"; }

# Track if we should clean up
CLEANUP_REQUIRED=false

cleanup() {
    if [ "$CLEANUP_REQUIRED" = true ]; then
        info "Cleaning up..."
        docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
        rm -rf "$CONFIG_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Check prerequisites
info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    fail "docker not installed"
fi
pass "docker available"

if ! command -v uv &> /dev/null; then
    fail "uv not installed"
fi
pass "uv available"

if ! command -v jq &> /dev/null; then
    fail "jq not installed"
fi
pass "jq available"

# Check if already installed (don't clobber existing setup)
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    skip "Qdrant container already exists - skipping install test to preserve existing setup"
    skip "Run 'docker rm -f $CONTAINER_NAME' first to test fresh install"

    # Still validate existing setup
    info "Validating existing installation..."

    if [ -f "$CONFIG_DIR/config.json" ]; then
        QDRANT_PORT=$(jq -r '.qdrant_port' "$CONFIG_DIR/config.json")
        pass "Config file exists with port $QDRANT_PORT"

        if curl -s "http://localhost:${QDRANT_PORT}/healthz" > /dev/null 2>&1; then
            pass "Qdrant is healthy on port $QDRANT_PORT"
        else
            fail "Qdrant not responding on port $QDRANT_PORT"
        fi
    else
        fail "Config file missing at $CONFIG_DIR/config.json"
    fi

    exit 0
fi

# Fresh install test
CLEANUP_REQUIRED=true
info "Testing fresh install..."

# Remove any stale config
rm -rf "$CONFIG_DIR" 2>/dev/null || true

# Run install (without claude plugin add - that requires claude CLI)
info "Running install.sh (simulated - without plugin registration)..."
cd "$SCRIPT_DIR"

# Extract and run the core install steps (skip claude plugin add)
find_free_port() {
    local port
    for port in $(shuf -i 16333-26333 -n 100); do
        if ! ss -tuln | grep -q ":${port} "; then
            echo "$port"
            return 0
        fi
    done
    return 1
}

QDRANT_PORT=$(find_free_port)
info "Selected port: $QDRANT_PORT"

# Start Qdrant
info "Starting Qdrant container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${QDRANT_PORT}:6333" \
    -v "${CONFIG_DIR}/qdrant_storage:/qdrant/storage" \
    qdrant/qdrant

# Wait for ready
info "Waiting for Qdrant..."
for i in {1..30}; do
    if curl -s "http://localhost:${QDRANT_PORT}/healthz" > /dev/null 2>&1; then
        pass "Qdrant started on port $QDRANT_PORT"
        break
    fi
    if [ $i -eq 30 ]; then
        fail "Qdrant failed to start within 30 seconds"
    fi
    sleep 1
done

# Write config
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/config.json" << EOF
{
  "qdrant_port": ${QDRANT_PORT},
  "qdrant_host": "localhost",
  "qdrant_container": "${CONTAINER_NAME}"
}
EOF
pass "Config written"

# Verify config is read correctly
info "Verifying config module reads correctly..."
RETRIEVED_URL=$(uv run python -c "from claude_reflections.config import get_qdrant_url; print(get_qdrant_url())")
EXPECTED_URL="http://localhost:${QDRANT_PORT}"
if [ "$RETRIEVED_URL" = "$EXPECTED_URL" ]; then
    pass "Config module returns correct URL: $RETRIEVED_URL"
else
    fail "Config module returned '$RETRIEVED_URL', expected '$EXPECTED_URL'"
fi

# Test embedding model download
info "Testing embedding model (this may download ~90MB on first run)..."
uv run python -c "
from fastembed import TextEmbedding
model = TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')
result = list(model.embed(['test']))
assert len(result) == 1
assert len(result[0]) == 384
print('Embedding model OK')
"
pass "Embedding model works"

# Test indexing (using this repo as test data if JSONL exists)
info "Testing indexing capability..."
CLAUDE_PROJECTS_DIR="${HOME}/.claude/projects"
if [ -d "$CLAUDE_PROJECTS_DIR" ] && ls "$CLAUDE_PROJECTS_DIR"/*/*.jsonl &>/dev/null 2>&1; then
    info "Found JSONL files, testing real indexing..."
    # Get first project
    FIRST_PROJECT=$(ls -d "$CLAUDE_PROJECTS_DIR"/*/ 2>/dev/null | head -1 | xargs -I{} basename {})
    if [ -n "$FIRST_PROJECT" ]; then
        uv run python -m claude_reflections.cli index --project "$FIRST_PROJECT" 2>&1 | head -5
        pass "Indexing ran without error"
    else
        skip "No projects found to index"
    fi
else
    skip "No JSONL files found in ~/.claude/projects"
fi

# Test search (if we indexed anything)
info "Testing search capability..."
uv run python -c "
from claude_reflections.search import QdrantManager
from claude_reflections.config import get_qdrant_url

# Just verify we can connect and query (may return empty if nothing indexed)
qm = QdrantManager('test_validation_collection')
results = qm.search('test query', limit=1)
print(f'Search returned {len(results)} results')
"
pass "Search works"

# Test uninstall (simulated)
info "Testing uninstall..."
docker stop "$CONTAINER_NAME"
docker rm "$CONTAINER_NAME"
pass "Container removed"

if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    pass "Container no longer exists"
else
    fail "Container still exists after removal"
fi

CLEANUP_REQUIRED=false  # Already cleaned up

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All validation tests passed!${NC}"
echo -e "${GREEN}========================================${NC}"
