---
name: reflections
description: Search past conversation history and answer questions about previous project discussions. Use when asked about "how did we...", "what was our approach to...", or any question requiring context from past conversations. On first use, check installation status.
context: fork
agent: general-purpose
allowed-tools: Bash, Read
---

# Search Conversation History

Search past conversations to answer: $ARGUMENTS

## Environment

- Plugin directory: `~/.claude/plugins/local-marketplace/plugins/claude-reflections`
- Project name formula: strip leading `/`, replace `/` with `-`, prepend `-`
  - Example: `/home/corona/foo` → `-home-corona-foo`

## Workflow

1. **Search conversations:**
   ```bash
   cd ~/.claude/plugins/local-marketplace/plugins/claude-reflections
   uv run claude-reflections search "SEARCH_TERMS" --project="PROJECT_NAME" --limit 5
   ```
   - Extract search terms from the user's question
   - Derive project name from the working directory
   - Search auto-indexes the project incrementally before searching
   - **On failure**: if the command exits non-zero with a "Could not connect to Qdrant" error, tell the user: "The reflections system appears to be down. Run `./install.sh` in `~/.claude/plugins/local-marketplace/plugins/claude-reflections` or see [install.md](install.md) for troubleshooting."

2. **Read matched conversations:**
   For each search result, use Read to examine the JSONL file at the returned line number (±10 lines for context).

3. **Synthesize answer:**
   Extract relevant information and provide a clear answer. Cite conversation dates if helpful.

## CLI Reference

All commands run from the plugin directory.

```bash
PLUGIN_DIR=~/.claude/plugins/local-marketplace/plugins/claude-reflections
cd "$PLUGIN_DIR"

# List all indexed projects
uv run claude-reflections list

# Check indexing status for a project
uv run claude-reflections status --project="-home-corona-foo"

# Search (auto-indexes when --project specified)
uv run claude-reflections search "query terms" --project="-home-corona-foo" --limit 5

# Manual full reindex
uv run claude-reflections index --project="-home-corona-foo" --full --verbose
```

### Search Output Format

```
1. [assistant] Score: 0.892
   Project: -home-corona-foo
   File: /home/corona/.claude/projects/-home-corona-foo/abc123.jsonl
   Line: 45
   Time: 2025-01-04T10:30:00+00:00
   Preview: We implemented authentication using...
```

## JSONL Format

Conversation files at `~/.claude/projects/<project>/*.jsonl` contain one JSON object per line:

```json
{"type":"user","timestamp":"2025-01-04T10:30:00Z","message":{"role":"user","content":"How do we handle auth?"}}
{"type":"assistant","timestamp":"2025-01-04T10:30:15Z","message":{"role":"assistant","content":[{"type":"text","text":"We use JWT..."}]}}
```

- `type`: "user" or "assistant"
- `timestamp`: ISO format
- `message.content`: text (user) or array of blocks (assistant)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Qdrant not running | `docker start claude-reflections-qdrant` or run install.sh |
| No search results | Check project is indexed: `uv run claude-reflections list` |
| Wrong project name | Verify with `pwd \| sed 's\|^/\|-\|' \| tr '/' '-'` |
| CLI errors | See [install.md](install.md) for full troubleshooting |

For installation or configuration issues, direct the user to [install.md](install.md).
