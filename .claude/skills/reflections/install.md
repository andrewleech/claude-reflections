# Installation Guide

Complete installation instructions for the claude-reflections conversation memory system.

## Prerequisites

- Docker (for Qdrant vector database)
- Python >=3.11
- uv (Python package manager)

## Automated Installation

The easiest way to install is using the provided install script:

```bash
# Navigate to plugin directory (installed via marketplace symlink)
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
cd "$PLUGIN_DIR"
./install.sh
```

This will:
1. Start Qdrant v1.16 in Docker on a random available port (16333-26333)
2. Create configuration file at `~/.claude/reflections/config.json` with the chosen port
3. Install Python dependencies
4. Download embedding model (`sentence-transformers/all-MiniLM-L6-v2`)
5. Create plugin symlink in local marketplace
6. Create skill files in `.claude/skills/reflections/`

**After installation, restart Claude Code** to load the plugin and skill.

## Manual Installation

If you prefer to install manually or the script fails:

### 1. Start Qdrant Container

```bash
# Choose any available port (e.g., 16333, or check with: ss -tuln | grep :16333)
QDRANT_PORT=16333

# Start Qdrant v1.16 (pinned for API compatibility)
docker run -d --name claude-reflections-qdrant \
  -p ${QDRANT_PORT}:6333 \
  -v ~/.claude/reflections/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:v1.16

# Wait for Qdrant to be ready
sleep 5
curl -s http://localhost:${QDRANT_PORT}/healthz || echo "Qdrant not ready yet"
```

### 2. Create Configuration File

```bash
mkdir -p ~/.claude/reflections

# Use the same port as above
QDRANT_PORT=16333

cat > ~/.claude/reflections/config.json << EOF
{
  "qdrant_port": ${QDRANT_PORT},
  "qdrant_host": "localhost",
  "qdrant_container": "claude-reflections-qdrant"
}
EOF
```

### 3. Install Python Dependencies

```bash
# Replace with your actual plugin location if different
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
cd "$PLUGIN_DIR"
uv sync
```

### 4. Download Embedding Model

```bash
# Pre-download the embedding model to avoid first-use delay
cd "$PLUGIN_DIR"
uv run python -c "
from fastembed import TextEmbedding
model = TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')
print('Embedding model downloaded')
"
```

### 5. Create Plugin Marketplace Structure

```bash
# Create local marketplace
mkdir -p ~/.claude/plugins/local-marketplace/.claude-plugin
mkdir -p ~/.claude/plugins/local-marketplace/plugins

# Create marketplace manifest
cat > ~/.claude/plugins/local-marketplace/.claude-plugin/marketplace.json << 'EOF'
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "local",
  "description": "Local development plugins",
  "owner": {"name": "local-user"},
  "plugins": [{
    "name": "claude-reflections",
    "description": "Minimal conversation memory with vector search",
    "version": "0.2.0",
    "source": "./plugins/claude-reflections",
    "category": "productivity"
  }]
}
EOF

# Symlink plugin (assuming plugin is already at this location)
# If installing from a different location, adjust the source path
ln -sf "${PLUGIN_DIR}" \
  ~/.claude/plugins/local-marketplace/plugins/claude-reflections
```

### 6. Register Marketplace in Claude Code Settings

Add to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "claude-reflections@local": true
  },
  "extraKnownMarketplaces": {
    "local": {
      "source": {
        "source": "directory",
        "path": "$HOME/.claude/plugins/local-marketplace"
      }
    }
  }
}
```

Use `jq` to merge if settings file already exists:

```bash
MARKETPLACE_DIR="${HOME}/.claude/plugins/local-marketplace"
jq --arg mp_path "$MARKETPLACE_DIR" '. + {
  "enabledPlugins": (.enabledPlugins // {} | . + {"claude-reflections@local": true}),
  "extraKnownMarketplaces": (.extraKnownMarketplaces // {} | . + {
    "local": {
      "source": {
        "source": "directory",
        "path": $mp_path
      }
    }
  })
}' ~/.claude/settings.json > ~/.claude/settings.json.tmp && \
mv ~/.claude/settings.json.tmp ~/.claude/settings.json
```

### 7. Restart Claude Code

Exit and restart Claude Code for the plugin to load.

## Verification

After installation:

1. **Check plugin is installed:**
   - In Claude Code, type: "What plugins are installed?"
   - Should see: `claude-reflections` listed

2. **Check skill is available:**
   - In Claude Code, type: "What skills are available?"
   - Should see: `reflections` skill listed

3. **Check Qdrant is running:**
   ```bash
   docker ps | grep claude-reflections-qdrant
   # Check port from config file
   QDRANT_PORT=$(jq -r '.qdrant_port' ~/.claude/reflections/config.json)
   curl -s http://localhost:${QDRANT_PORT}/healthz
   ```

4. **Test CLI commands:**
   ```bash
   PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
   cd "$PLUGIN_DIR" && uv run claude-reflections list
   ```

## First-Time Indexing

After installation, index your current project:

```bash
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
cd "$PLUGIN_DIR" && uv run claude-reflections index --project="$PROJECT" --verbose
```

Or search will automatically index incrementally when using `--project`:

```bash
cd "$PLUGIN_DIR" && uv run claude-reflections search "test query" --project="$PROJECT"
```

## Configuration

### Qdrant Connection

Configuration is stored in `~/.claude/reflections/config.json`:

```json
{
  "qdrant_port": 16333,
  "qdrant_host": "localhost",
  "qdrant_container": "claude-reflections-qdrant"
}
```

Override with environment variable:
```bash
export QDRANT_URL="http://localhost:16333"
```

### State Directory

By default, state files are stored in `~/.claude/reflections/`.

Override with environment variable:
```bash
export REFLECTIONS_STATE_DIR="/path/to/state"
```

### Embedding Model

Default: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)

To change, modify `EMBEDDING_MODEL` and `EMBEDDING_DIM` in `src/claude_reflections/search.py`.

## Troubleshooting

| Issue | Check | Solution |
|-------|-------|----------|
| Qdrant not running | `docker ps \| grep qdrant` | `docker start claude-reflections-qdrant` or re-run install.sh |
| Wrong port | `cat ~/.claude/reflections/config.json` | Update port or restart Qdrant on correct port |
| CLI not found | `which uv` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Plugin not loading | Check `~/.claude/settings.json` | Ensure enabledPlugins and extraKnownMarketplaces are set |
| Skill not appearing | Restart Claude Code | Plugin must be loaded first |
| Empty search results | Check if indexed | `uv run claude-reflections list` |
| Permission denied | Check file ownership | `sudo chown -R $(whoami) ~/.claude/reflections` |

## Uninstallation

To remove claude-reflections:

```bash
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
cd "$PLUGIN_DIR"
./uninstall.sh
```

This will:
- Stop and remove Qdrant container
- Remove plugin symlink
- Optionally remove data directory (`~/.claude/reflections/`)

## Getting Help

- Check [README.md](../../README.md) for usage examples
- Check [CLAUDE.md](../../CLAUDE.md) for architecture details
- Report issues at: https://github.com/corona/claude-reflections/issues (if applicable)
