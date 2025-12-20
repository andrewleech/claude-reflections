"""Tests for state management."""

from __future__ import annotations

from pathlib import Path

from claude_reflections.state import FileState, ProjectState, StateManager


class TestFileState:
    """Tests for FileState dataclass."""

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        state = FileState(
            last_byte_offset=1000,
            indexed_count=50,
            last_indexed="2025-01-15T10:00:00Z",
        )
        result = state.to_dict()
        assert result["last_byte_offset"] == 1000
        assert result["indexed_count"] == 50
        assert result["last_indexed"] == "2025-01-15T10:00:00Z"

    def test_from_dict(self) -> None:
        """Should create from dictionary."""
        data = {
            "last_byte_offset": 2000,
            "indexed_count": 100,
            "last_indexed": "2025-01-15T12:00:00Z",
        }
        state = FileState.from_dict(data)
        assert state.last_byte_offset == 2000
        assert state.indexed_count == 100
        assert state.last_indexed == "2025-01-15T12:00:00Z"

    def test_from_dict_defaults(self) -> None:
        """Should use defaults for missing fields."""
        state = FileState.from_dict({})
        assert state.last_byte_offset == 0
        assert state.indexed_count == 0
        assert state.last_indexed == ""


class TestProjectState:
    """Tests for ProjectState dataclass."""

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        state = ProjectState(
            collection_name="reflections_test",
            files={
                "file1.jsonl": FileState(last_byte_offset=100, indexed_count=10),
            },
        )
        result = state.to_dict()
        assert result["collection_name"] == "reflections_test"
        assert "file1.jsonl" in result["files"]
        assert result["files"]["file1.jsonl"]["last_byte_offset"] == 100

    def test_from_dict(self) -> None:
        """Should create from dictionary."""
        data = {
            "collection_name": "reflections_project",
            "files": {
                "a.jsonl": {"last_byte_offset": 50, "indexed_count": 5},
            },
        }
        state = ProjectState.from_dict(data)
        assert state.collection_name == "reflections_project"
        assert "a.jsonl" in state.files
        assert state.files["a.jsonl"].last_byte_offset == 50


class TestStateManager:
    """Tests for StateManager."""

    def test_load_creates_default(self, state_dir: Path) -> None:
        """Loading nonexistent state creates default."""
        manager = StateManager(state_dir)
        state = manager.load("new-project")

        assert state.collection_name.startswith("reflections_")
        assert len(state.files) == 0

    def test_save_and_load(self, state_dir: Path) -> None:
        """Should persist state correctly."""
        manager = StateManager(state_dir)

        # Create and save state
        state = ProjectState(
            collection_name="reflections_test",
            files={
                "conv.jsonl": FileState(last_byte_offset=500, indexed_count=25),
            },
        )
        manager.save("test-project", state)

        # Load and verify
        loaded = manager.load("test-project")
        assert loaded.collection_name == "reflections_test"
        assert loaded.files["conv.jsonl"].last_byte_offset == 500
        assert loaded.files["conv.jsonl"].indexed_count == 25

    def test_update_file_state(self, state_dir: Path) -> None:
        """Should update file state incrementally."""
        manager = StateManager(state_dir)

        # First update
        manager.update_file_state("project1", "file.jsonl", 100, 10)
        state = manager.load("project1")
        assert state.files["file.jsonl"].last_byte_offset == 100
        assert state.files["file.jsonl"].indexed_count == 10

        # Second update (incremental)
        manager.update_file_state("project1", "file.jsonl", 200, 5)
        state = manager.load("project1")
        assert state.files["file.jsonl"].last_byte_offset == 200
        assert state.files["file.jsonl"].indexed_count == 15  # 10 + 5

    def test_get_file_offset(self, state_dir: Path) -> None:
        """Should get file offset or 0 if not found."""
        manager = StateManager(state_dir)

        # No state yet
        offset = manager.get_file_offset("project", "file.jsonl")
        assert offset == 0

        # After update
        manager.update_file_state("project", "file.jsonl", 500, 10)
        offset = manager.get_file_offset("project", "file.jsonl")
        assert offset == 500

    def test_list_projects(self, state_dir: Path) -> None:
        """Should list all projects with state files."""
        manager = StateManager(state_dir)

        # Initially empty
        projects = manager.list_projects()
        assert projects == []

        # Add some projects
        manager.save("project-a", ProjectState(collection_name="col_a"))
        manager.save("project-b", ProjectState(collection_name="col_b"))

        projects = manager.list_projects()
        assert sorted(projects) == ["project-a", "project-b"]

    def test_get_stats(self, state_dir: Path) -> None:
        """Should get project statistics."""
        manager = StateManager(state_dir)
        manager.update_file_state("project", "file1.jsonl", 100, 10)
        manager.update_file_state("project", "file2.jsonl", 200, 20)

        stats = manager.get_stats("project")
        assert stats["project"] == "project"
        assert stats["files_tracked"] == 2
        assert stats["total_indexed"] == 30
