"""JSONL conversation parser with incremental indexing support."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IndexableMessage:
    """A message extracted from JSONL ready for indexing."""

    uuid: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    session_id: str
    file_path: str
    line_number: int
    byte_offset: int  # Start of this line in file


def extract_text_content(message_content: str | list[dict]) -> str:
    """Extract text content from a message.

    User messages have string content.
    Assistant messages have array content with type: "text", "thinking", "tool_use", etc.
    We only extract text blocks.
    """
    if isinstance(message_content, str):
        return message_content

    # Assistant content is an array of blocks
    text_parts: list[str] = []
    for block in message_content:
        if isinstance(block, dict):
            block_type = block.get("type", "")
            # Only extract text blocks, skip thinking and tool_use
            if block_type == "text":
                text_parts.append(block.get("text", ""))
    return "\n".join(text_parts)


def parse_jsonl_line(line: str) -> dict | None:
    """Parse a single JSONL line, returning None if invalid or skippable."""
    line = line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Skip non-message types
    msg_type = data.get("type", "")
    if msg_type not in ("user", "assistant"):
        return None

    return data


def iter_new_messages(
    file_path: str | Path,
    start_offset: int = 0,
) -> Iterator[IndexableMessage]:
    """Iterate over messages in a JSONL file starting from a byte offset.

    Args:
        file_path: Path to the JSONL file
        start_offset: Byte offset to start reading from (for incremental indexing)

    Yields:
        IndexableMessage for each valid user/assistant message
    """
    file_path = Path(file_path)

    with open(file_path, "rb") as f:
        # Seek to start position
        f.seek(start_offset)

        # If not at start, skip to next line boundary
        if start_offset > 0:
            # Read until newline to get to a clean line boundary
            f.readline()

        line_number = 0
        if start_offset > 0:
            # Count lines up to offset for accurate line numbers
            f.seek(0)
            for _ in f:
                line_number += 1
                if f.tell() >= start_offset:
                    break
            f.seek(start_offset)
            if start_offset > 0:
                f.readline()  # Skip partial line

        while True:
            byte_offset = f.tell()
            line_bytes = f.readline()
            if not line_bytes:
                break

            line_number += 1
            line = line_bytes.decode("utf-8", errors="replace")
            data = parse_jsonl_line(line)

            if data is None:
                continue

            msg_type = data.get("type", "")
            message = data.get("message", {})
            content_raw = message.get("content", "")

            # Extract text content
            content = extract_text_content(content_raw)
            if not content.strip():
                continue

            yield IndexableMessage(
                uuid=data.get("uuid", ""),
                role=msg_type,
                content=content,
                timestamp=data.get("timestamp", ""),
                session_id=data.get("sessionId", ""),
                file_path=str(file_path),
                line_number=line_number,
                byte_offset=byte_offset,
            )


def get_final_offset(file_path: str | Path) -> int:
    """Get the final byte offset of a file (i.e., file size)."""
    return Path(file_path).stat().st_size


def discover_jsonl_files(project_dir: str | Path) -> list[Path]:
    """Discover all JSONL files in a project directory."""
    project_dir = Path(project_dir)
    if not project_dir.exists():
        return []
    return sorted(project_dir.glob("*.jsonl"))


def get_projects_dir() -> Path:
    """Get the Claude projects directory."""
    return Path(os.path.expanduser("~/.claude/projects"))


def list_all_projects() -> list[str]:
    """List all project names in the Claude projects directory."""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []

    return sorted(d.name for d in projects_dir.iterdir() if d.is_dir() and any(d.glob("*.jsonl")))


def get_project_path(project_name: str) -> Path:
    """Get the path to a project directory."""
    return get_projects_dir() / project_name
