#!/bin/bash
set -e

# Read hook input from stdin
INPUT=$(cat)

# Extract current working directory from session to determine project
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')

if [ -z "$CWD" ]; then
    exit 0
fi

# Convert path to project name (e.g., /home/corona/foo -> -home-corona-foo)
PROJECT=$(echo "$CWD" | sed 's|^/||; s|/|-|g')

if [ -n "$PROJECT" ]; then
    cd "${CLAUDE_PLUGIN_ROOT}"
    uv run python -m claude_reflections.cli index --project "$PROJECT" 2>/dev/null || true
fi

exit 0
