"""Pytest fixtures for claude-reflections tests."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_jsonl_content() -> str:
    """Sample JSONL conversation content."""
    lines = [
        {
            "type": "user",
            "uuid": "user-001",
            "message": {"role": "user", "content": "How do I fix the Docker memory issue?"},
            "timestamp": "2025-01-15T10:00:00Z",
            "sessionId": "session-123",
        },
        {
            "type": "assistant",
            "uuid": "asst-001",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "Let me think about this..."},
                    {
                        "type": "text",
                        "text": "The Docker memory issue can be fixed by setting resource limits.",
                    },
                ],
            },
            "timestamp": "2025-01-15T10:00:05Z",
            "sessionId": "session-123",
        },
        {
            "type": "file-history-snapshot",
            "messageId": "snap-001",
            "snapshot": {},
        },
        {
            "type": "user",
            "uuid": "user-002",
            "message": {"role": "user", "content": "Can you show me an example?"},
            "timestamp": "2025-01-15T10:01:00Z",
            "sessionId": "session-123",
        },
    ]
    return "\n".join(json.dumps(line) for line in lines)


@pytest.fixture
def sample_jsonl_file(temp_dir: Path, sample_jsonl_content: str) -> Path:
    """Create a sample JSONL file for testing."""
    jsonl_path = temp_dir / "conversation.jsonl"
    jsonl_path.write_text(sample_jsonl_content)
    return jsonl_path


@pytest.fixture
def sample_project_dir(temp_dir: Path, sample_jsonl_content: str) -> Path:
    """Create a sample project directory structure."""
    project_dir = temp_dir / "projects" / "-home-user-myproject"
    project_dir.mkdir(parents=True)

    # Create a few JSONL files
    (project_dir / "session1.jsonl").write_text(sample_jsonl_content)
    (project_dir / "session2.jsonl").write_text(sample_jsonl_content)

    return project_dir


@pytest.fixture
def state_dir(temp_dir: Path) -> Path:
    """Create a temporary state directory."""
    state_path = temp_dir / "reflections"
    state_path.mkdir()
    return state_path
