#!/bin/bash
cd "$(dirname "$0")"
exec uv run python -m claude_reflections.server
