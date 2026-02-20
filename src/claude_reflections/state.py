"""Per-project state management for incremental indexing."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class FileState:
    """State for a single JSONL file."""

    last_byte_offset: int = 0
    indexed_count: int = 0
    last_indexed: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_byte_offset": self.last_byte_offset,
            "indexed_count": self.indexed_count,
            "last_indexed": self.last_indexed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileState:
        return cls(
            last_byte_offset=data.get("last_byte_offset", 0),
            indexed_count=data.get("indexed_count", 0),
            last_indexed=data.get("last_indexed", ""),
        )


@dataclass
class ProjectState:
    """State for a project's indexing progress."""

    collection_name: str
    files: dict[str, FileState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection_name": self.collection_name,
            "files": {name: fs.to_dict() for name, fs in self.files.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectState:
        return cls(
            collection_name=data.get("collection_name", ""),
            files={
                name: FileState.from_dict(fs_data)
                for name, fs_data in data.get("files", {}).items()
            },
        )


class StateManager:
    """Manages per-project state files in ~/.claude/reflections/<project>/."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            base_dir = os.environ.get(
                "REFLECTIONS_STATE_DIR",
                os.path.expanduser("~/.claude/reflections"),
            )
        self.base_dir = Path(base_dir)

    def _project_dir(self, project: str) -> Path:
        """Get the state directory for a project."""
        # Sanitize project name for filesystem
        safe_name = project.replace("/", "-").lstrip("-")
        return self.base_dir / safe_name

    def _state_file(self, project: str) -> Path:
        """Get the state file path for a project."""
        return self._project_dir(project) / "state.json"

    def get_db_path(self, project: str) -> Path:
        """Get the vector database path for a project."""
        return self._project_dir(project) / "vectors.db"

    def load(self, project: str) -> ProjectState:
        """Load state for a project, creating default if not exists."""
        state_file = self._state_file(project)

        if not state_file.exists():
            # Create default state with collection name
            safe_name = project.replace("/", "-").replace("-", "_").lstrip("_")
            return ProjectState(collection_name=f"reflections_{safe_name}")

        with open(state_file, encoding="utf-8") as f:
            data = json.load(f)

        return ProjectState.from_dict(data)

    def save(self, project: str, state: ProjectState) -> None:
        """Save state for a project."""
        state_file = self._state_file(project)
        state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

    def update_file_state(
        self,
        project: str,
        filename: str,
        byte_offset: int,
        new_count: int,
    ) -> None:
        """Update the state for a specific file after indexing."""
        state = self.load(project)

        if filename not in state.files:
            state.files[filename] = FileState()

        file_state = state.files[filename]
        file_state.last_byte_offset = byte_offset
        file_state.indexed_count += new_count
        file_state.last_indexed = datetime.now(UTC).isoformat()

        self.save(project, state)

    def get_file_offset(self, project: str, filename: str) -> int:
        """Get the last indexed byte offset for a file."""
        state = self.load(project)
        if filename in state.files:
            return state.files[filename].last_byte_offset
        return 0

    def list_projects(self) -> list[str]:
        """List all projects with state files."""
        if not self.base_dir.exists():
            return []

        projects = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and (item / "state.json").exists():
                projects.append(item.name)
        return sorted(projects)

    def get_stats(self, project: str) -> dict[str, Any]:
        """Get statistics for a project."""
        state = self.load(project)
        total_indexed = sum(fs.indexed_count for fs in state.files.values())
        return {
            "project": project,
            "collection_name": state.collection_name,
            "files_tracked": len(state.files),
            "total_indexed": total_indexed,
        }
