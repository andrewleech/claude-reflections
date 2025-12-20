# claude-reflections

Minimal conversation memory with vector search and Claude Agent SDK retrieval.

## Overview

`claude-reflections` is a Claude Code plugin that indexes your past conversations and makes them searchable. When you search, it returns file references pointing back to the original JSONL files, then uses a Claude Agent SDK agent to read the context and answer your questions.

### Key Features

- **No persistent services** (except Qdrant for vector storage)
- **Reversible indexing** - vectors point back to original JSONL files
- **Per-project isolation** - each project has its own collection and state
- **Incremental indexing** - only processes new messages on each run
- **Stop hook integration** - automatically indexes when conversations end

## Architecture

```
+----------------+     +----------------+     +----------------+
|  Claude Code   | --> |   MCP Server   | --> |     Qdrant     |
|  (stop hook)   |     |  (indexing +   |     |  (vectors with |
+----------------+     |   search)      |     |  file:line ref)|
                       +-------+--------+     +----------------+
                               |
                               v on search
                       +----------------+
                       | Claude Agent   |
                       | SDK (read-only |
                       |  reads JSONL)  |
                       +----------------+
```

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Qdrant running locally (default: `http://localhost:6333`)

### As Claude Code Plugin

```bash
# Install from local path
claude plugin add /path/to/claude-reflections

# Or from GitHub (when published)
claude plugin add https://github.com/youruser/claude-reflections
```

### Manual Installation

```bash
# Clone and setup
cd ~/claude-reflections
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

## Usage

### MCP Tools (via Claude Code)

Once installed as a plugin, these tools are available in Claude Code:

- **search** - Search past conversations
  ```
  search("Docker memory issues", project="my-project", limit=5)
  ```

- **answer** - Search and get detailed answers using the Agent SDK
  ```
  answer("How did we fix the authentication bug?", project="my-project")
  ```

- **index_status** - Check indexing status
  ```
  index_status(project="my-project")
  ```

- **reindex** - Manually trigger reindexing
  ```
  reindex(project="my-project", full=True)
  ```

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
5. **Search**: Vector similarity search returns file references
6. **Answer**: Agent SDK reads original files around the matched lines to provide answers

## License

MIT
