---
name: reflections
description: Search past conversation history and answer questions about previous project discussions. Use when asked about "how did we...", "what was our approach to...", or any question requiring context from past conversations. On first use, check installation status.
allowed-tools: Bash, Read, Glob, Grep
---

# Conversation Reflections

Search and analyze past conversations from this project's history using vector-based semantic search.

## Installation Check

On first use, verify the indexing system is installed and running:

```bash
# Set plugin directory (installed via marketplace symlink)
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"

# Check if Qdrant is running
docker ps | grep claude-reflections-qdrant || echo "Not installed - see [install.md](install.md)"

# Check if claude-reflections CLI is available
cd "$PLUGIN_DIR" && uv run claude-reflections list 2>/dev/null || echo "CLI not available - see [install.md](install.md)"
```

If not installed, refer to [install.md](install.md) for setup instructions.

**Note:** All CLI commands require running from the plugin directory. Set `PLUGIN_DIR` at the start of your workflow.

## When to Use This Skill

- User asks "how did we fix X?"
- User asks "what approach did we take for Y?"
- User needs context from previous discussions
- User wants to search conversation history

## Project Name Conversion

Claude Code stores conversations in `~/.claude/projects/<sanitized-path>/`.
Convert current directory to project name:

```bash
# Formula: Strip leading `/`, replace `/` with `-`, prepend `-`
PROJECT=$(pwd | sed 's|^/|-|g' | tr '/' '-')
echo "Current project: $PROJECT"
```

Examples:
- `/home/corona/foo` → `-home-corona-foo`
- `/mnt/bulk/nas/navdy/client` → `-mnt-bulk-nas-navdy-client`

## Available Commands

**All commands assume `PLUGIN_DIR` is set:**
```bash
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
```

### List All Indexed Projects
```bash
cd "$PLUGIN_DIR" && uv run claude-reflections list
```

### Check if Current Project is Indexed
```bash
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
cd "$PLUGIN_DIR" && uv run claude-reflections status --project="$PROJECT"
```

### Search Conversations

**When searching with `--project` specified, search automatically indexes that project first (incremental).**

```bash
# Search all projects (no auto-indexing)
cd "$PLUGIN_DIR" && uv run claude-reflections search "docker configuration" --limit 10

# Search specific project (with auto-indexing)
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
cd "$PLUGIN_DIR" && uv run claude-reflections search "authentication bug" --project="$PROJECT" --limit 5
```

### Index Current Project Manually
```bash
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
cd "$PLUGIN_DIR" && uv run claude-reflections index --project="$PROJECT" --verbose
```

### Full Reindex (from scratch)
```bash
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
cd "$PLUGIN_DIR" && uv run claude-reflections index --project="$PROJECT" --full --verbose
```

## Workflow for Answering Questions

When user asks about past conversations:

1. **Set up environment:**
   ```bash
   PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
   PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
   ```

2. **Search for relevant conversations:**
   ```bash
   cd "$PLUGIN_DIR" && uv run claude-reflections search "query text" --project="$PROJECT" --limit 5
   ```

3. **Review search results:**
   - Each result shows: file path, line number, score, snippet, timestamp
   - Example output:
     ```
     1. [assistant] Score: 0.892
        Project: -mnt-bulk-nas-navdy-client
        File: /home/corona/.claude/projects/-mnt-bulk-nas-navdy-client/abc123.jsonl
        Line: 45
        Time: 2025-01-04T10:30:00+00:00
        Preview: We implemented authentication using...
     ```

4. **Read relevant JSONL files:**
   ```bash
   # Read around the matched line (±10 lines for context)
   Read /home/corona/.claude/projects/-mnt-bulk-nas-navdy-client/abc123.jsonl --offset 35 --limit 20
   ```

5. **Synthesize answer:**
   - Extract relevant information from JSONL content
   - Provide answer based on actual conversation context
   - Cite specific conversations/timestamps if helpful

## JSONL File Format

Conversation files contain one JSON object per line:

```json
{"type":"user","uuid":"...","timestamp":"2025-01-04T10:30:00Z","message":{"role":"user","content":"How do we handle auth?"}}
{"type":"assistant","uuid":"...","timestamp":"2025-01-04T10:30:15Z","message":{"role":"assistant","content":[{"type":"text","text":"We use JWT tokens..."}]}}
```

Key fields:
- `type`: "user" or "assistant"
- `timestamp`: ISO format timestamp
- `message.content`: Text content (string for user, array of blocks for assistant)

## Examples

### Example 1: Find bug fix approach

User asks: "How did we fix the authentication bug?"

```bash
# 1. Set up environment
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')

# 2. Search (auto-indexes first)
cd "$PLUGIN_DIR" && uv run claude-reflections search "authentication bug fix" --project="$PROJECT" --limit 5

# 3. Read relevant files (from search results)
Read /home/corona/.claude/projects/$PROJECT/conversation-abc123.jsonl --offset 100 --limit 20

# 4. Synthesize answer from JSONL content
```

### Example 2: Find implementation approach

User asks: "What's our Docker strategy?"

```bash
# 1. Set up environment
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"

# 2. Search across all projects (no auto-indexing)
cd "$PLUGIN_DIR" && uv run claude-reflections search "docker strategy" --limit 10

# 3. Review top results from multiple projects
# 4. Read relevant sections from multiple JSONL files
# 5. Compile comprehensive answer
```

### Example 3: Check if project is indexed

User asks: "What have we discussed about X?"

```bash
# 1. Set up environment and check status
PLUGIN_DIR="${HOME}/.claude/plugins/local-marketplace/plugins/claude-reflections"
PROJECT=$(pwd | sed 's|^/|-|' | tr '/' '-')
cd "$PLUGIN_DIR" && uv run claude-reflections status --project="$PROJECT"

# 2. If not indexed or needs updating:
cd "$PLUGIN_DIR" && uv run claude-reflections index --project="$PROJECT"

# 3. Then proceed with search
```

## Tips

- **Search auto-indexes:** When using `--project`, search automatically runs incremental indexing first. Without `--project`, searches all projects but doesn't auto-index (for speed)
- **Use specific queries:** More specific search terms yield better results
- **Read context:** Always read ±10 lines around matched results for full context
- **Multiple projects:** Search without `--project` to find results across all indexed projects
- **Check installation:** On first use, verify Qdrant is running and CLI is available
- **Plugin directory:** All commands must run from `$PLUGIN_DIR` - set this variable at the start of your workflow
