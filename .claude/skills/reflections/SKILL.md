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

- Plugin: ~/.claude/plugins/local-marketplace/plugins/claude-reflections
- Project name: convert working directory to project name by stripping leading `/`, replacing `/` with `-`, prepending `-`
  - Example: /home/corona/foo → -home-corona-foo

## Workflow

1. Check Qdrant is running:
   ```bash
   docker ps | grep claude-reflections-qdrant
   ```
   If not running, report "reflections not installed - run install.sh in the plugin directory" and stop.

2. Search conversations (auto-indexes the project first):
   ```bash
   cd ~/.claude/plugins/local-marketplace/plugins/claude-reflections
   uv run claude-reflections search "SEARCH_TERMS" --project="PROJECT_NAME" --limit 5
   ```
   Extract search terms from the user's question. Use the project name derived from the working directory.

3. For each search result, use Read to examine the JSONL file at the returned line number (±10 lines for context).

   JSONL format:
   - `type`: "user" or "assistant"
   - `timestamp`: ISO format
   - `message.content`: the text content

4. Synthesize an answer from the conversation content. Cite timestamps or conversation dates if relevant.

If no relevant results found, report that clearly.
