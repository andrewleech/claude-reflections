# claude-reflections - Action Guide

## Overview

Minimal conversation memory system for Claude Code:
- **Single dependency**: Qdrant only (no batch services, no background daemons)
- **Pointer-based storage**: Vectors reference file:line, not duplicated content
- **On-demand retrieval**: Claude Agent SDK reads original JSONL when needed
- **Per-project isolation**: Separate collections and state per project

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Code    │────▶│   MCP Server    │────▶│     Qdrant      │
│  (stop hook)    │     │  (FastMCP)      │     │  (vectors +     │
└─────────────────┘     └────────┬────────┘     │  file:line refs)│
                                 │              └─────────────────┘
                                 ▼ on answer()
                        ┌─────────────────┐
                        │ Claude Agent SDK│
                        │ (read-only)     │
                        └─────────────────┘
```

## Quick Start

### Automated Install
```bash
cd /path/to/claude-reflections
./install.sh
```

This will:
- Start Qdrant in Docker on a random available port
- Save config to `~/.claude/reflections/config.json`
- Pre-download the embedding model
- Install the plugin system-wide (`~/.claude`)

### Uninstall
```bash
./uninstall.sh
```

### Manual Install (if needed)
```bash
# Start Qdrant manually
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Install plugin
claude plugin add /path/to/claude-reflections --scope user
```

### Manual CLI Usage
```bash
cd /home/corona/claude-reflections
uv run claude-reflections index              # Index all projects
uv run claude-reflections search "docker"    # Search conversations
uv run claude-reflections status             # Check indexing status
uv run claude-reflections list               # List available projects
```

## MCP Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `search` | Find relevant past conversations | `search("docker memory issues")` |
| `answer` | Search + Agent reads context + answers | `answer("how did we fix the auth bug?")` |
| `index_status` | Show indexing statistics | `index_status()` |
| `reindex` | Force reindex a project | `reindex("my-project", full=True)` |

## Key Files

| File | Purpose |
|------|---------|
| `src/claude_reflections/server.py` | FastMCP server with 4 tools |
| `src/claude_reflections/indexer.py` | JSONL parser, byte offset tracking |
| `src/claude_reflections/search.py` | FastEmbed embeddings, Qdrant operations |
| `src/claude_reflections/agent.py` | Claude Agent SDK wrapper (read-only) |
| `src/claude_reflections/state.py` | Per-project state management |
| `src/claude_reflections/cli.py` | CLI commands |

## Data Flow

### Indexing (via stop hook or CLI)
1. Glob `~/.claude/projects/*/*.jsonl`
2. Parse each line → extract user/assistant text (skip thinking, tool_use)
3. Generate 384d embeddings (FastEmbed, all-MiniLM-L6-v2)
4. Store in Qdrant with payload: `{file_path, line_number, role, snippet, timestamp}`
5. Track byte offset in `~/.claude/reflections/<project>/state.json`

### Search
1. Embed query → vector similarity search in Qdrant
2. Return `{file_path, line_number, score, snippet}` for each match

### Answer
1. Search for relevant results
2. Spawn Claude Agent SDK agent with `allowed_tools=["Read"]`
3. Agent reads original JSONL around matched line numbers
4. Agent synthesizes answer from full context

## State Files

```
~/.claude/reflections/
├── config.json         # {qdrant_port, qdrant_host, qdrant_container}
├── qdrant_storage/     # Qdrant persistent storage (Docker volume)
├── my-project/
│   └── state.json      # {files: {name: {offset, count}}, collection_name}
└── other-project/
    └── state.json
```

## Development

### Run Tests
```bash
uv run pytest -v                    # All tests
uv run pytest -v -m "not integration"  # Skip Qdrant-dependent tests
```

### Lint & Format
```bash
uv run ruff check .                 # Check
uv run ruff check . --fix           # Auto-fix
uv run ruff format .                # Format
```

### Type Check
```bash
uv run mypy src/
```

## Troubleshooting

| Symptom | Check | Fix |
|---------|-------|-----|
| No search results | `docker ps \| grep claude-reflections-qdrant` | Run `./install.sh` |
| Wrong Qdrant port | `cat ~/.claude/reflections/config.json` | Re-run `./install.sh` |
| Empty index | `claude-reflections status` | `claude-reflections index --full` |
| Agent SDK errors | Check claude-code-sdk installed | `uv add claude-code-sdk` |
| "Collection not found" | Project never indexed | `claude-reflections index -p project-name` |

## Configuration

### Config File
`~/.claude/reflections/config.json` (created by install.sh):
```json
{
  "qdrant_port": 16789,
  "qdrant_host": "localhost",
  "qdrant_container": "claude-reflections-qdrant"
}
```

### Environment Variables (override config file)
- `QDRANT_URL` - Qdrant endpoint (overrides config file if set)
- `REFLECTIONS_STATE_DIR` - State directory (default: `~/.claude/reflections`)

### Embedding Model
Default: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)

To change, modify `EMBEDDING_MODEL` and `EMBEDDING_DIM` in `search.py`.

## Differences from claude-self-reflect

| Aspect | claude-self-reflect | claude-reflections |
|--------|---------------------|-------------------|
| Services | Qdrant + batch-watcher + batch-monitor | Qdrant only |
| Storage | Full narratives in Qdrant | Pointers to JSONL |
| Indexing | Background Docker services | Stop hook / CLI |
| Retrieval | Direct payload | Agent reads files |
| AI processing | Batch API narratives | Agent SDK on-demand |
| Complexity | High | Low |

## Plugin Files

- `install.sh` - Automated install (Qdrant, embedding model, plugin)
- `uninstall.sh` - Remove plugin and Qdrant container
- `.claude-plugin/plugin.json` - Plugin manifest
- `.mcp.json` - MCP server configuration
- `.claude/settings.json` - Stop hook for auto-indexing
- `hooks/stop-index.sh` - Indexing script triggered on conversation end
- `run-mcp.sh` - MCP server launcher
- `src/claude_reflections/config.py` - Config file management

## Critical Rules

1. **No content duplication**: Qdrant stores pointers, not full messages
2. **Read-only agents**: Agent SDK gets `allowed_tools=["Read"]` only
3. **Incremental indexing**: Track byte offsets, only index new content
4. **Per-project isolation**: Each project has its own collection and state
