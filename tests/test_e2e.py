"""End-to-end integration tests.

These tests exercise the full flow: indexing -> search -> retrieval.
No external services required (sqlite-vec is embedded).

Run with: pytest tests/test_e2e.py -v -m e2e
Skip with: pytest -v -m "not e2e"
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_reflections.indexer import IndexableMessage, iter_new_messages
from claude_reflections.search import SqliteVecManager
from claude_reflections.state import StateManager

pytestmark = pytest.mark.e2e


@pytest.fixture
def sample_conversation() -> str:
    """Sample JSONL conversation data."""
    messages = [
        {
            "type": "user",
            "uuid": "e2e-user-001",
            "message": {"role": "user", "content": "How do I configure nginx reverse proxy?"},
            "timestamp": "2025-01-15T10:00:00Z",
            "sessionId": "e2e-session-001",
        },
        {
            "type": "assistant",
            "uuid": "e2e-asst-001",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "To configure nginx as a reverse proxy, edit /etc/nginx/nginx.conf "
                        "and add a location block with proxy_pass directive.",
                    }
                ],
            },
            "timestamp": "2025-01-15T10:00:05Z",
            "sessionId": "e2e-session-001",
        },
        {
            "type": "user",
            "uuid": "e2e-user-002",
            "message": {"role": "user", "content": "What about SSL termination?"},
            "timestamp": "2025-01-15T10:01:00Z",
            "sessionId": "e2e-session-001",
        },
        {
            "type": "assistant",
            "uuid": "e2e-asst-002",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "For SSL termination, configure listen 443 ssl, "
                        "add ssl_certificate and ssl_certificate_key directives.",
                    }
                ],
            },
            "timestamp": "2025-01-15T10:01:05Z",
            "sessionId": "e2e-session-001",
        },
    ]
    return "\n".join(json.dumps(m) for m in messages)


@pytest.fixture
def temp_project(tmp_path: Path, sample_conversation: str) -> tuple[Path, Path]:
    """Create temporary project structure mimicking ~/.claude/projects/."""
    projects_dir = tmp_path / "projects" / "-home-user-testproject"
    projects_dir.mkdir(parents=True)

    jsonl_file = projects_dir / "session.jsonl"
    jsonl_file.write_text(sample_conversation)

    state_dir = tmp_path / "reflections"
    state_dir.mkdir()

    return projects_dir, state_dir


class TestEndToEndFlow:
    """End-to-end tests for the full indexing and search flow."""

    def test_index_and_search_flow(
        self,
        temp_project: tuple[Path, Path],
        tmp_path: Path,
    ) -> None:
        """Full flow: parse JSONL -> index -> search -> verify results."""
        projects_dir, state_dir = temp_project
        jsonl_file = projects_dir / "session.jsonl"
        db_path = tmp_path / "project" / "vectors.db"

        # Step 1: Parse JSONL
        messages = list(iter_new_messages(jsonl_file, start_offset=0))
        assert len(messages) == 4  # 2 user + 2 assistant

        # Step 2: Index into sqlite-vec
        manager = SqliteVecManager(db_path)
        indexed_count = manager.index_messages(messages)
        assert indexed_count == 4

        # Step 3: Search for nginx content
        results = manager.search("nginx reverse proxy configuration", limit=5)
        assert len(results) > 0

        # Should find the nginx-related messages
        snippets = [r.snippet.lower() for r in results]
        assert any("nginx" in s for s in snippets)

        # Step 4: Search for SSL content
        ssl_results = manager.search("SSL certificate setup", limit=5)
        assert len(ssl_results) > 0
        assert any("ssl" in r.snippet.lower() for r in ssl_results)

        # Step 5: Verify collection stats
        stats = manager.get_collection_stats()
        assert stats["points_count"] == 4
        assert stats["status"] == "ok"

        manager.close()

    def test_incremental_indexing(
        self,
        temp_project: tuple[Path, Path],
        tmp_path: Path,
    ) -> None:
        """Test that incremental indexing works via byte offsets."""
        projects_dir, state_dir = temp_project
        jsonl_file = projects_dir / "session.jsonl"
        db_path = tmp_path / "project" / "vectors.db"

        # First indexing pass
        messages1 = list(iter_new_messages(jsonl_file, start_offset=0))
        manager = SqliteVecManager(db_path)
        count1 = manager.index_messages(messages1)
        assert count1 == 4

        # Simulate getting final offset
        with open(jsonl_file, "rb") as f:
            f.seek(0, 2)  # End of file
            final_offset = f.tell()

        # Append new message
        new_message = {
            "type": "user",
            "uuid": "e2e-user-003",
            "message": {"role": "user", "content": "How do I enable HTTP/2?"},
            "timestamp": "2025-01-15T10:02:00Z",
            "sessionId": "e2e-session-001",
        }
        with open(jsonl_file, "a") as f:
            f.write("\n" + json.dumps(new_message))

        # Second indexing pass (incremental)
        messages2 = list(iter_new_messages(jsonl_file, start_offset=final_offset))
        assert len(messages2) == 1  # Only the new message

        count2 = manager.index_messages(messages2)
        assert count2 == 1

        # Verify total
        stats = manager.get_collection_stats()
        assert stats["points_count"] == 5

        manager.close()

    def test_state_manager_integration(
        self,
        temp_project: tuple[Path, Path],
        tmp_path: Path,
    ) -> None:
        """Test StateManager tracks indexing progress correctly."""
        projects_dir, state_dir = temp_project
        jsonl_file = projects_dir / "session.jsonl"

        state_mgr = StateManager(state_dir)
        project_name = "testproject"

        # Initial state
        initial_offset = state_mgr.get_file_offset(project_name, jsonl_file.name)
        assert initial_offset == 0

        # Index and update state
        messages = list(iter_new_messages(jsonl_file, start_offset=0))
        db_path = state_mgr.get_db_path(project_name)
        manager = SqliteVecManager(db_path)
        manager.index_messages(messages)

        with open(jsonl_file, "rb") as f:
            f.seek(0, 2)
            final_offset = f.tell()

        state_mgr.update_file_state(
            project_name,
            jsonl_file.name,
            byte_offset=final_offset,
            new_count=len(messages),
        )

        # Verify state persisted
        new_offset = state_mgr.get_file_offset(project_name, jsonl_file.name)
        assert new_offset == final_offset

        stats = state_mgr.get_stats(project_name)
        assert stats["total_indexed"] == 4
        assert stats["files_tracked"] == 1

        manager.close()

    def test_search_relevance(self, tmp_path: Path) -> None:
        """Test that search returns relevant results ranked by similarity."""
        db_path = tmp_path / "project" / "vectors.db"

        # Create messages with distinct topics
        messages = [
            IndexableMessage(
                uuid="rel-001",
                role="user",
                content="How do I install Python packages with pip?",
                timestamp="2025-01-15T10:00:00Z",
                session_id="rel-session",
                file_path="/test.jsonl",
                line_number=1,
                byte_offset=0,
            ),
            IndexableMessage(
                uuid="rel-002",
                role="user",
                content="What is the best way to manage Docker containers?",
                timestamp="2025-01-15T10:01:00Z",
                session_id="rel-session",
                file_path="/test.jsonl",
                line_number=2,
                byte_offset=100,
            ),
            IndexableMessage(
                uuid="rel-003",
                role="user",
                content="How do I create a Python virtual environment?",
                timestamp="2025-01-15T10:02:00Z",
                session_id="rel-session",
                file_path="/test.jsonl",
                line_number=3,
                byte_offset=200,
            ),
        ]

        manager = SqliteVecManager(db_path)
        manager.index_messages(messages)

        # Search for Python-related content
        results = manager.search("Python pip install packages", limit=3)

        # First result should be about pip
        assert "pip" in results[0].snippet.lower() or "python" in results[0].snippet.lower()

        # Docker message should have lower score for Python query
        docker_scores = [r.score for r in results if "docker" in r.snippet.lower()]
        python_scores = [r.score for r in results if "python" in r.snippet.lower()]

        if docker_scores and python_scores:
            assert max(python_scores) > max(docker_scores)

        manager.close()
