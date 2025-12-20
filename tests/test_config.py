"""Tests for config module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from claude_reflections.config import (
    ReflectionsConfig,
    get_config_path,
    get_qdrant_url,
    load_config,
    save_config,
)


class TestReflectionsConfig:
    """Tests for ReflectionsConfig dataclass."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        config = ReflectionsConfig()
        assert config.qdrant_port == 6333
        assert config.qdrant_host == "localhost"
        assert config.qdrant_container == "claude-reflections-qdrant"

    def test_qdrant_url_property(self) -> None:
        """Should construct URL from host and port."""
        config = ReflectionsConfig(qdrant_host="192.168.1.100", qdrant_port=16789)
        assert config.qdrant_url == "http://192.168.1.100:16789"

    def test_to_dict(self) -> None:
        """Should serialize to dict."""
        config = ReflectionsConfig(qdrant_port=12345, qdrant_container="test-container")
        data = config.to_dict()
        assert data["qdrant_port"] == 12345
        assert data["qdrant_host"] == "localhost"
        assert data["qdrant_container"] == "test-container"

    def test_from_dict(self) -> None:
        """Should deserialize from dict."""
        data = {
            "qdrant_port": 9999,
            "qdrant_host": "qdrant.local",
            "qdrant_container": "my-qdrant",
        }
        config = ReflectionsConfig.from_dict(data)
        assert config.qdrant_port == 9999
        assert config.qdrant_host == "qdrant.local"
        assert config.qdrant_container == "my-qdrant"

    def test_from_dict_missing_fields(self) -> None:
        """Should use defaults for missing fields."""
        config = ReflectionsConfig.from_dict({"qdrant_port": 7777})
        assert config.qdrant_port == 7777
        assert config.qdrant_host == "localhost"  # default
        assert config.qdrant_container == "claude-reflections-qdrant"  # default


class TestConfigPath:
    """Tests for config path resolution."""

    def test_default_path(self) -> None:
        """Should use default path when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove REFLECTIONS_STATE_DIR if present
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

    def test_env_url_takes_precedence(self, tmp_path: Path) -> None:
        """QDRANT_URL env var should override config file."""
        # Write a config file
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"qdrant_port": 1111}))

        with patch.dict(
            os.environ,
            {
                "QDRANT_URL": "http://override-host:9999",
                "REFLECTIONS_STATE_DIR": str(tmp_path),
            },
        ):
            config = load_config()
            assert config.qdrant_host == "override-host"
            assert config.qdrant_port == 9999

    def test_env_url_with_scheme(self) -> None:
        """Should parse URL with http:// scheme."""
        with patch.dict(os.environ, {"QDRANT_URL": "http://myhost:8888"}):
            config = load_config()
            assert config.qdrant_host == "myhost"
            assert config.qdrant_port == 8888

    def test_env_url_https_scheme(self) -> None:
        """Should parse URL with https:// scheme."""
        with patch.dict(os.environ, {"QDRANT_URL": "https://secure.qdrant.io:443"}):
            config = load_config()
            assert config.qdrant_host == "secure.qdrant.io"
            assert config.qdrant_port == 443

    def test_env_url_no_scheme(self) -> None:
        """Should handle URL without scheme."""
        with patch.dict(os.environ, {"QDRANT_URL": "bare-host:7777"}):
            config = load_config()
            assert config.qdrant_host == "bare-host"
            assert config.qdrant_port == 7777

    def test_env_url_host_only(self) -> None:
        """Should handle host-only URL (no port)."""
        with patch.dict(os.environ, {"QDRANT_URL": "http://hostonly"}):
            config = load_config()
            assert config.qdrant_host == "hostonly"

    def test_load_from_file(self, tmp_path: Path) -> None:
        """Should load config from file when no env var."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "qdrant_port": 16333,
                    "qdrant_host": "file-host",
                    "qdrant_container": "file-container",
                }
            )
        )

        with patch.dict(
            os.environ,
            {"REFLECTIONS_STATE_DIR": str(tmp_path)},
            clear=False,
        ):
            # Ensure QDRANT_URL is not set
            os.environ.pop("QDRANT_URL", None)
            config = load_config()
            assert config.qdrant_port == 16333
            assert config.qdrant_host == "file-host"
            assert config.qdrant_container == "file-container"

    def test_load_defaults_when_no_file(self, tmp_path: Path) -> None:
        """Should return defaults when no config file exists."""
        with patch.dict(
            os.environ,
            {"REFLECTIONS_STATE_DIR": str(tmp_path)},
            clear=False,
        ):
            os.environ.pop("QDRANT_URL", None)
            config = load_config()
            assert config.qdrant_port == 6333
            assert config.qdrant_host == "localhost"


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        config_dir = tmp_path / "nested" / "path"
        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(config_dir)}):
            config = ReflectionsConfig(qdrant_port=11111)
            save_config(config)

            config_file = config_dir / "config.json"
            assert config_file.exists()

            data = json.loads(config_file.read_text())
            assert data["qdrant_port"] == 11111

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Should overwrite existing config file."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"qdrant_port": 1}))

        with patch.dict(os.environ, {"REFLECTIONS_STATE_DIR": str(tmp_path)}):
            save_config(ReflectionsConfig(qdrant_port=2))

            data = json.loads(config_file.read_text())
            assert data["qdrant_port"] == 2


class TestGetQdrantUrl:
    """Tests for get_qdrant_url convenience function."""

    def test_returns_url_string(self, tmp_path: Path) -> None:
        """Should return URL as string."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"qdrant_port": 19999, "qdrant_host": "test"}))

        with patch.dict(
            os.environ,
            {"REFLECTIONS_STATE_DIR": str(tmp_path)},
            clear=False,
        ):
            os.environ.pop("QDRANT_URL", None)
            url = get_qdrant_url()
            assert url == "http://test:19999"
