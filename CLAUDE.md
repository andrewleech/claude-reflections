# claude-reflections - Action Guide

## Overview

Minimal conversation memory system for Claude Code:
- **Single dependency**: Qdrant only (no batch services, no background daemons)
- **Pointer-based storage**: Vectors reference file:line, not duplicated content
- **Skill-based retrieval**: Reflections skill reads original JSONL files when you ask about past conversations
- **Per-project isolation**: Separate collections and state per project
- **Auto-indexing**: Search command automatically indexes before searching (incremental)

## Version Requirements

- **Qdrant Server**: v1.16.x (Docker image: `qdrant/qdrant:v1.16`)
- **qdrant-client**: ~=1.16.0 (Python client library)
- **Python**: >=3.11

These versions are pinned for API compatibility. The v1.16 API introduced `query_points()` replacing the older `search()` method.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Code    │────▶│   Skill         │────▶│  CLI Commands   │
│  (user asks     │     │  (reflections)  │     │  (index +       │
│   question)     │     │                 │     │   search)       │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │     Qdrant      │
                                                 │  (vectors +     │
                                                 │  file:line refs)│
                                                 └─────────────────┘

Workflow:
1. User asks: "How did we fix X?"
2. Skill determines project from $PWD
3. Skill runs CLI: uv run claude-reflections search "X"
4. CLI auto-indexes (incremental), then searches
5. Skill reads JSONL files at returned line numbers
6. Skill provides answer from actual conversation content
```

## Quick Start

### Automated Install
```bash
cd /path/to/claude-reflections
./install.sh
```

This will:
- Start Qdrant v1.16 in Docker on a random available port
- Save config to `~/.claude/reflections/config.json`
- Pre-download the embedding model
- Create local marketplace at `~/.claude/plugins/local-marketplace`
- Symlink plugin into marketplace structure
- Update `~/.claude/settings.json` with plugin configuration

**After installation, restart Claude Code and verify:**
- Ask: "What skills are available?" → should show `reflections`
- Ask: "What plugins are installed?" → should show `claude-reflections`

### Uninstall
```bash
./uninstall.sh
```

### Manual Install (if needed)
```bash
# Start Qdrant manually (v1.16 pinned for API compatibility)
docker run -d --name claude-reflections-qdrant \
  -p 6333:6333 \
  -v ~/.claude/reflections/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:v1.16

# Create local marketplace structure
mkdir -p ~/.claude/plugins/local-marketplace/.claude-plugin
mkdir -p ~/.claude/plugins/local-marketplace/plugins

# Symlink plugin
ln -s /path/to/claude-reflections \
  ~/.claude/plugins/local-marketplace/plugins/claude-reflections

# Add to ~/.claude/settings.json:
# "enabledPlugins": {"claude-reflections@local": true},
# "extraKnownMarketplaces": {"local": {"source": {"source": "directory", "path": "~/.claude/plugins/local-marketplace"}}}

# Restart Claude Code
```

### Manual CLI Usage
```bash
cd /home/corona/claude-reflections
uv run claude-reflections index              # Index all projects
uv run claude-reflections search "docker"    # Search conversations
uv run claude-reflections status             # Check indexing status
uv run claude-reflections list               # List available projects
```

## Skill Usage

The **reflections** skill is automatically triggered when you ask about past conversations:

**Example questions:**
- "How did we fix the authentication bug?"
- "What approach did we take for Docker configuration?"
- "What have we discussed about X?"

The skill automatically:
1. Determines the current project name from your working directory (`$PWD`)
2. Runs the CLI search command (with auto-indexing)
3. Reads relevant JSONL files for full context
4. Provides synthesized answers from actual conversations

**Search auto-indexes**: The search command automatically runs incremental indexing before searching, ensuring results are always up-to-date.

For complete skill documentation, see [`.claude/skills/reflections/SKILL.md`](.claude/skills/reflections/SKILL.md).

## Key Files

| File | Purpose |
|------|---------|
| `.claude/skills/reflections/SKILL.md` | Skill implementation with tool usage |
| `.claude/skills/reflections/install.md` | Installation reference documentation |
| `src/claude_reflections/cli.py` | CLI commands (index, search, status, list) |
| `src/claude_reflections/indexer.py` | JSONL parser, byte offset tracking |
| `src/claude_reflections/search.py` | FastEmbed embeddings, Qdrant operations |
| `src/claude_reflections/state.py` | Per-project state management |
| `src/claude_reflections/config.py` | Configuration file management |

## Data Flow

### Indexing (automatic on search)
1. Glob `~/.claude/projects/*/*.jsonl`
2. Parse each line → extract user/assistant text (skip thinking, tool_use)
3. Generate 384d embeddings (FastEmbed, all-MiniLM-L6-v2)
4. Store in Qdrant with payload: `{file_path, line_number, role, snippet, timestamp}`
5. Track byte offset in `~/.claude/reflections/<project>/state.json`

### Search (via CLI)
1. Run incremental indexing first (auto-index)
2. Embed query → vector similarity search in Qdrant
3. Return `{file_path, line_number, score, snippet}` for each match

### Skill Workflow
1. User asks about past conversations
2. Skill determines project name from working directory
3. Skill runs CLI search command
4. Skill reads JSONL files at returned line numbers (using Read tool)
5. Skill synthesizes answer from actual conversation content

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
| "Collection not found" | Project never indexed | `claude-reflections index -p project-name` |
| API errors (search/query) | Qdrant version mismatch | Ensure Qdrant v1.16 and qdrant-client ~=1.16.0 |
| Skill not available | Plugin not loaded | Add `"claude-reflections@local": true` to enabledPlugins in settings.json |
| "Plugin not found in marketplace" | Wrong marketplace source path | Verify `source.path` in extraKnownMarketplaces points to marketplace root |
| Invalid settings error | Wrong marketplace source format | Use `{"source": "directory", "path": "..."}` not `"source": "directory"` |

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
| Indexing | Background Docker services | CLI with auto-indexing |
| Retrieval | Direct payload | Skill reads files |
| AI processing | Batch API narratives | Skill reads JSONL directly |
| Complexity | High | Low |

## Plugin Files

- `install.sh` - Automated install (Qdrant, embedding model, plugin)
- `uninstall.sh` - Remove plugin and Qdrant container
- `.claude-plugin/plugin.json` - Plugin manifest (references skill)
- `.claude/skills/reflections/SKILL.md` - Skill implementation with tool usage
- `.claude/skills/reflections/install.md` - Installation reference documentation
- `src/claude_reflections/cli.py` - CLI commands with auto-indexing
- `src/claude_reflections/config.py` - Config file management

## Critical Rules

1. **No content duplication**: Qdrant stores pointers, not full messages
2. **Skill reads original files**: Skills use Read tool to access JSONL at referenced line numbers
3. **Incremental indexing**: Track byte offsets, only index new content
4. **Per-project isolation**: Each project has its own collection and state
5. **Auto-indexing on search**: CLI search command automatically runs incremental indexing before searching
