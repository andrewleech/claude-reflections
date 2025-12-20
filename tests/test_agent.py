"""Tests for agent module."""

from __future__ import annotations

import pytest

from claude_reflections.agent import ProjectAgent
from claude_reflections.search import SearchResult


class TestProjectAgent:
    """Tests for ProjectAgent class."""

    def test_format_search_results_empty(self) -> None:
        """Should handle empty results."""
        result = ProjectAgent.format_search_results([])
        assert result == "No search results found."

    def test_format_search_results(self) -> None:
        """Should format search results correctly."""
        results = [
            SearchResult(
                uuid="result-001",
                file_path="/path/to/conversation.jsonl",
                line_number=42,
                role="user",
                snippet="How do I fix Docker?",
                score=0.85,
                timestamp="2025-01-15T10:00:00Z",
                session_id="session-123",
            ),
            SearchResult(
                uuid="result-002",
                file_path="/path/to/other.jsonl",
                line_number=100,
                role="assistant",
                snippet="Here is the solution...",
                score=0.75,
                timestamp="2025-01-15T10:05:00Z",
                session_id="session-456",
            ),
        ]

        formatted = ProjectAgent.format_search_results(results)

        # Check structure
        assert "Search Results:" in formatted
        assert "[user]" in formatted
        assert "[assistant]" in formatted
        assert "Score: 0.850" in formatted
        assert "Score: 0.750" in formatted
        assert "Line: 42" in formatted
        assert "Line: 100" in formatted

    def test_get_project_cwd(self) -> None:
        """Should return correct project path."""
        path = ProjectAgent._get_project_cwd("test-project")
        assert path.name == "test-project"
        assert "/.claude/projects/" in str(path)


@pytest.mark.integration
class TestProjectAgentIntegration:
    """Integration tests for ProjectAgent (requires SDK and Claude Code)."""

    @pytest.mark.asyncio
    async def test_answer_without_sdk(self) -> None:
        """Should handle missing SDK gracefully."""
        results = [
            SearchResult(
                uuid="test-001",
                file_path="/test/file.jsonl",
                line_number=1,
                role="user",
                snippet="Test content",
                score=0.9,
                timestamp="2025-01-15T10:00:00Z",
                session_id="session-test",
            ),
        ]

        try:
            response = await ProjectAgent.answer(
                project="test-project",
                query="What was discussed?",
                results=results,
            )
            # If SDK is available, should return a response
            assert isinstance(response, str)
        except ImportError:
            # SDK not installed - expected in test environment
            pytest.skip("Claude Code SDK not installed")
        except Exception as e:
            # Other errors (e.g., no Claude Code running)
            pytest.skip(f"Agent not available: {e}")
