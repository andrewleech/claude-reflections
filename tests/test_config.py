"""Tests for config module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from claude_reflections.config import (
    get_config_path,
    get_state_base_dir,
    is_legacy_qdrant_config,
    load_config,
    save_config,
)


class TestStateBaseDir:
    """Tests for get_state_base_dir."""

    def test_default_path(self) -> None:
        """Should use default path when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("REFLECTIONS_STATE_DIR", None)
            path = get_state_base_dir()
            assert path == Path.home() / ".claude" / "reflections"

    def test_env_override(self, tmp_path: Path) -> None:
        """Should use env var when set."""
        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(tmp_path)}):
            path = get_state_base_dir()
            assert path == tmp_path


class TestConfigPath:
    """Tests for config path resolution."""

    def test_default_path(self) -> None:
        """Should use default path when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("REFLECTIONS_STATE_DIR", None)
            path = get_config_path()
            assert path == Path.home() / ".claude" / "reflections" / "config.json"

    def test_env_override_path(self, tmp_path: Path) -> None:
        """Should use env var when set."""
        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(tmp_path)}):
            path = get_config_path()
            assert path == tmp_path / "config.json"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Should load config from file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"version": 2}))

        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(tmp_path)}):
            config = load_config()
            assert config["version"] == 2

    def test_load_defaults_when_no_file(self, tmp_path: Path) -> None:
        """Should return empty dict when no config file exists."""
        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(tmp_path)}):
            config = load_config()
            assert config == {}


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        config_dir = tmp_path / "nested" / "path"
        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(config_dir)}):
            save_config({"version": 2})

            config_file = config_dir / "config.json"
            assert config_file.exists()

            data = json.loads(config_file.read_text())
            assert data["version"] == 2

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Should overwrite existing config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"version": 1}))

        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(tmp_path)}):
            save_config({"version": 2})

            data = json.loads(config_file.read_text())
            assert data["version"] == 2


class TestLegacyDetection:
    """Tests for legacy Qdrant config detection."""

    def test_detects_qdrant_config(self) -> None:
        """Should detect old Qdrant-based config."""
        old_config = {
            "qdrant_port": 16333,
            "qdrant_host": "localhost",
            "qdrant_container": "claude-reflections-qdrant",
        }
        assert is_legacy_qdrant_config(old_config) is True

    def test_does_not_flag_new_config(self) -> None:
        """Should not flag new config format."""
        new_config = {"version": 2}
        assert is_legacy_qdrant_config(new_config) is False

    def test_empty_config(self) -> None:
        """Should not flag empty config."""
        assert is_legacy_qdrant_config({}) is False
