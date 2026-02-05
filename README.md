# claude-reflections

Minimal conversation memory with vector search.

## Overview

`claude-reflections` is a Claude Code plugin that indexes your past conversations and makes them searchable. The **reflections** skill is automatically triggered when you ask about past conversations, searches for relevant context, and reads the original JSONL files to provide detailed answers.

### Key Features

- **No persistent services** (except Qdrant for vector storage)
- **Reversible indexing** - vectors point back to original JSONL files
- **Per-project isolation** - each project has its own collection and state
- **Incremental indexing** - only processes new messages on each run
- **Auto-indexing on search** - search automatically indexes before searching
- **Skill-based integration** - automatically triggered by conversation questions

## Architecture

```
+----------------+     +----------------+     +----------------+
|  Claude Code   | --> |     Skill      | --> |  CLI Commands  |
|  (user asks    |     |  (reflections) |     |  (index +      |
|   question)    |     |                |     |   search)      |
+----------------+     +----------------+     +--------+-------+
                                                       |
                                                       v
                                              +----------------+
                                              |     Qdrant     |
                                              |  (vectors with |
                                              |  file:line ref)|
                                              +----------------+

Skill workflow:
1. User asks: "How did we fix X?"
2. Skill determines project name from $PWD
3. Skill runs: uv run claude-reflections search "X"
4. CLI auto-indexes (incremental), then searches
5. Skill reads JSONL files at returned line numbers
6. Skill synthesizes answer from actual conversation content
```

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for Qdrant)
- Qdrant v1.16 (pinned in install.sh)

### Automated Install (Recommended)

```bash
cd /path/to/claude-reflections
./install.sh
```

This will:
- Start Qdrant v1.16 in Docker on a random available port
- Install Python dependencies (qdrant-client ~=1.16.0)
- Download the embedding model
- Create local marketplace at `~/.claude/plugins/local-marketplace`
- Symlink plugin into marketplace
- Update `~/.claude/settings.json` with plugin configuration

**After installation:**
1. Restart Claude Code
2. Verify installation:
   - Ask: "What skills are available?" → should show `reflections`
   - Ask: "What plugins are installed?" → should show `claude-reflections`
3. Try asking: "How did we implement X?" to trigger the skill

### Manual Installation

If you prefer manual setup:

1. **Start Qdrant:**
   ```bash
   docker run -d --name claude-reflections-qdrant \
     -p 6333:6333 \
     -v ~/.claude/reflections/qdrant_storage:/qdrant/storage \
     qdrant/qdrant:v1.16
   ```

2. **Install Python dependencies:**
   ```bash
   cd /path/to/claude-reflections
   uv sync
   ```

3. **Create local marketplace:**
   ```bash
   mkdir -p ~/.claude/plugins/local-marketplace/.claude-plugin
   mkdir -p ~/.claude/plugins/local-marketplace/plugins

   # Symlink plugin
   ln -s /path/to/claude-reflections \
     ~/.claude/plugins/local-marketplace/plugins/claude-reflections
   ```

4. **Create marketplace manifest:**
   ```bash
   cat > ~/.claude/plugins/local-marketplace/.claude-plugin/marketplace.json << 'EOF'
   {
     "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
     "name": "local",
     "description": "Local development plugins",
     "owner": {"name": "your-name"},
     "plugins": [{
       "name": "claude-reflections",
       "description": "Minimal conversation memory with vector search",
       "version": "0.2.0",
       "source": "./plugins/claude-reflections",
       "category": "productivity"
     }]
   }
   EOF
   ```

5. **Update Claude Code settings** (`~/.claude/settings.json`):
   ```json
   {
     "enabledPlugins": {
       "claude-reflections@local": true
     },
     "extraKnownMarketplaces": {
       "local": {
         "source": {
           "source": "directory",
           "path": "/home/YOUR_USER/.claude/plugins/local-marketplace"
         }
       }
     }
   }
   ```

6. **Restart Claude Code** for changes to take effect

### Development Setup

For development without the marketplace:

```bash
# Clone and setup
cd ~/claude-reflections
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

## Usage

### Skill Usage (via Claude Code)

Once installed, the **reflections** skill is automatically available in Claude Code. The skill is triggered when you ask questions about past conversations:

**Example questions:**
- "How did we fix the authentication bug?"
- "What approach did we take for Docker configuration?"
- "What have we discussed about X?"

The skill automatically:
1. Determines the current project from your working directory
2. Searches past conversations using vector similarity
3. Reads relevant JSONL files for full context
4. Provides synthesized answers based on actual conversations

**Search automatically indexes before searching** (incremental), ensuring results are always up-to-date.

See [`.claude/skills/reflections/SKILL.md`](.claude/skills/reflections/SKILL.md) for complete usage details.

### CLI Commands

```bash
# List available projects
claude-reflections list

# Index a project (incremental)
claude-reflections index --project my-project

# Full reindex
claude-reflections index --project my-project --full

# Search
claude-reflections search "Docker configuration" --project my-project

# Check status
claude-reflections status
```

## Configuration

### Environment Variables

- `QDRANT_URL` - Qdrant server URL (default: `http://localhost:6333`)
- `REFLECTIONS_STATE_DIR` - State directory (default: `~/.claude/reflections`)

### Per-Project State

Each project's state is stored in:
```
~/.claude/reflections/<project>/state.json
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check .
uv run ruff format --check .

# Run type checking
uv run mypy src/claude_reflections
```

## How It Works

1. **Indexing**: Parses JSONL files from `~/.claude/projects/<project>/*.jsonl`
2. **Content Extraction**: Extracts user prompts and assistant text responses (skips thinking blocks and tool use)
3. **Embedding**: Generates 384-dimensional embeddings using FastEmbed (all-MiniLM-L6-v2)
4. **Storage**: Stores vectors in Qdrant with payloads containing file path and line number
5. **Search**: CLI auto-indexes (incremental), then performs vector similarity search
6. **Skill**: Reads original JSONL files at returned line numbers to provide detailed answers

## License

MIT
