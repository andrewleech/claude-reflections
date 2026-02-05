---
name: reflections
description: Search past conversation history and answer questions about previous project discussions. Use when asked about "how did we...", "what was our approach to...", or any question requiring context from past conversations. On first use, check installation status.
allowed-tools: Task
---

# Conversation Reflections

Search and analyze past conversations using vector-based semantic search. This skill spawns an autonomous agent that searches, reads JSONL files, and synthesizes answers without blocking the main conversation.

## Usage

When the user asks about past conversations, use the Task tool to spawn an agent:

**Task parameters:**
- `subagent_type`: `"general-purpose"`
- `description`: `"Search conversation history"`
- `prompt`: Use the template below, substituting the user's question and current working directory

**Prompt template:**

```
Search past conversations to answer: "{USER_QUESTION}"

Working directory: {PWD}
Plugin directory: ~/.claude/plugins/local-marketplace/plugins/claude-reflections

## Project name
Convert working directory to project name:
- /home/corona/foo → -home-corona-foo
- Formula: strip leading /, replace / with -, prepend -

## Workflow

1. Check Qdrant is running:
   docker ps | grep claude-reflections-qdrant
   If not running, report "reflections not installed" and stop.

2. Search conversations (auto-indexes first):
   cd ~/.claude/plugins/local-marketplace/plugins/claude-reflections
   uv run claude-reflections search "{SEARCH_TERMS}" --project="{PROJECT_NAME}" --limit 5

3. For each result, read the JSONL file at the returned line number (±10 lines for context).
   JSONL format: {"type":"user"|"assistant", "timestamp":"...", "message":{"content":"..."}}

4. Synthesize an answer from the conversation content. Cite timestamps if relevant.

Return: A clear answer to the user's question based on past conversations, or report if nothing relevant was found.
```

## When to Use

- "How did we fix X?"
- "What approach did we take for Y?"
- "What have we discussed about Z?"
- Any question requiring context from past conversations

## Installation

If the agent reports Qdrant is not running, see [install.md](install.md).

## CLI Reference

```bash
PLUGIN_DIR=~/.claude/plugins/local-marketplace/plugins/claude-reflections
cd "$PLUGIN_DIR"

uv run claude-reflections list                                    # List projects
uv run claude-reflections status --project="-home-corona-foo"     # Check status
uv run claude-reflections search "query" --project="..." --limit 5  # Search
uv run claude-reflections index --project="..." --full            # Full reindex
```
