#!/bin/bash
# Temporary debug version to see what data the stop hook receives

INPUT=$(cat)

# Log the full input to inspect available fields
LOG_FILE="${HOME}/.claude/reflections/stop-hook-debug.log"
mkdir -p "$(dirname "$LOG_FILE")"

{
  echo "=== Stop hook fired at $(date) ==="
  echo "$INPUT" | jq '.' 2>/dev/null || echo "$INPUT"
  echo ""
} >> "$LOG_FILE"

exit 0
