"""Tests for JSONL indexer."""

from __future__ import annotations

from pathlib import Path

from claude_reflections.indexer import (
    discover_jsonl_files,
    extract_text_content,
    iter_new_messages,
    parse_jsonl_line,
)


class TestExtractTextContent:
    """Tests for extract_text_content function."""

    def test_string_content(self) -> None:
        """User messages have string content."""
        content = "Hello, how are you?"
        result = extract_text_content(content)
        assert result == "Hello, how are you?"

    def test_array_content_with_text(self) -> None:
        """Assistant messages have array content."""
        content = [
            {"type": "text", "text": "Here is the answer."},
        ]
        result = extract_text_content(content)
        assert result == "Here is the answer."

    def test_array_content_skips_thinking(self) -> None:
        """Thinking blocks should be skipped."""
        content = [
            {"type": "thinking", "thinking": "Let me think..."},
            {"type": "text", "text": "The answer is 42."},
        ]
        result = extract_text_content(content)
        assert result == "The answer is 42."

    def test_array_content_skips_tool_use(self) -> None:
        """Tool use blocks should be skipped."""
        content = [
            {"type": "tool_use", "name": "read", "input": {}},
            {"type": "text", "text": "I read the file."},
        ]
        result = extract_text_content(content)
        assert result == "I read the file."

    def test_multiple_text_blocks(self) -> None:
        """Multiple text blocks are joined."""
        content = [
            {"type": "text", "text": "First part."},
            {"type": "text", "text": "Second part."},
        ]
        result = extract_text_content(content)
        assert result == "First part.\nSecond part."


class TestParseJsonlLine:
    """Tests for parse_jsonl_line function."""

    def test_user_message(self) -> None:
        """Parse a user message."""
        line = '{"type": "user", "uuid": "123", "message": {"role": "user", "content": "Hi"}}'
        result = parse_jsonl_line(line)
        assert result is not None
        assert result["type"] == "user"
        assert result["uuid"] == "123"

    def test_assistant_message(self) -> None:
        """Parse an assistant message."""
        line = (
            '{"type": "assistant", "uuid": "456", "message": {"role": "assistant", "content": []}}'
        )
        result = parse_jsonl_line(line)
        assert result is not None
        assert result["type"] == "assistant"

    def test_skip_snapshot(self) -> None:
        """File history snapshots should be skipped."""
        line = '{"type": "file-history-snapshot", "snapshot": {}}'
        result = parse_jsonl_line(line)
        assert result is None

    def test_invalid_json(self) -> None:
        """Invalid JSON should return None."""
        result = parse_jsonl_line("not json")
        assert result is None

    def test_empty_line(self) -> None:
        """Empty lines should return None."""
        result = parse_jsonl_line("")
        assert result is None


class TestIterNewMessages:
    """Tests for iter_new_messages function."""

    def test_reads_all_messages(self, sample_jsonl_file: Path) -> None:
        """Should read all user and assistant messages."""
        messages = list(iter_new_messages(sample_jsonl_file))

        # Should have 3 messages (2 user, 1 assistant with text)
        assert len(messages) == 3

        # Check first message
        assert messages[0].uuid == "user-001"
        assert messages[0].role == "user"
        assert "Docker memory" in messages[0].content

        # Check second message (assistant)
        assert messages[1].uuid == "asst-001"
        assert messages[1].role == "assistant"
        assert "resource limits" in messages[1].content

    def test_incremental_reading(self, sample_jsonl_file: Path) -> None:
        """Should support reading from an offset."""
        # Get all messages first
        all_messages = list(iter_new_messages(sample_jsonl_file, start_offset=0))

        # Read from middle
        if len(all_messages) > 1:
            second_msg = all_messages[1]
            # Read from after second message should give fewer results
            messages_from_offset = list(
                iter_new_messages(sample_jsonl_file, start_offset=second_msg.byte_offset + 1)
            )
            assert len(messages_from_offset) < len(all_messages)

    def test_message_has_file_info(self, sample_jsonl_file: Path) -> None:
        """Messages should have file path and line number."""
        messages = list(iter_new_messages(sample_jsonl_file))
        assert len(messages) > 0

        msg = messages[0]
        assert msg.file_path == str(sample_jsonl_file)
        assert msg.line_number > 0
        assert msg.byte_offset >= 0


class TestDiscoverJsonlFiles:
    """Tests for discover_jsonl_files function."""

    def test_finds_jsonl_files(self, sample_project_dir: Path) -> None:
        """Should find all JSONL files in project directory."""
        files = discover_jsonl_files(sample_project_dir)
        assert len(files) == 2
        assert all(f.suffix == ".jsonl" for f in files)

    def test_returns_empty_for_nonexistent(self, temp_dir: Path) -> None:
        """Should return empty list for nonexistent directory."""
        files = discover_jsonl_files(temp_dir / "nonexistent")
        assert files == []

    def test_returns_sorted(self, sample_project_dir: Path) -> None:
        """Files should be sorted."""
        files = discover_jsonl_files(sample_project_dir)
        assert files == sorted(files)
