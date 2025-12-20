"""Configuration management for claude-reflections."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ReflectionsConfig:
    """Configuration for claude-reflections."""

    qdrant_port: int = 6333
    qdrant_host: str = "localhost"
    qdrant_container: str = "claude-reflections-qdrant"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "qdrant_port": self.qdrant_port,
            "qdrant_host": self.qdrant_host,
            "qdrant_container": self.qdrant_container,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReflectionsConfig:
        return cls(
            qdrant_port=data.get("qdrant_port", 6333),
            qdrant_host=data.get("qdrant_host", "localhost"),
            qdrant_container=data.get("qdrant_container", "claude-reflections-qdrant"),
        )


def get_config_path() -> Path:
    """Get the path to the config file."""
    base_dir = os.environ.get(
        "REFLECTIONS_STATE_DIR",
        os.path.expanduser("~/.claude/reflections"),
    )
    return Path(base_dir) / "config.json"


def load_config() -> ReflectionsConfig:
    """Load configuration, with environment variable override."""
    # Environment variable takes precedence
    env_url = os.environ.get("QDRANT_URL")
    if env_url:
        # Parse URL to extract host and port
        # Expected format: http://host:port
        url_part = env_url.split("://", 1)[1] if "://" in env_url else env_url
        if ":" in url_part:
            host, port_str = url_part.rsplit(":", 1)
            try:
                port = int(port_str)
                return ReflectionsConfig(qdrant_host=host, qdrant_port=port)
            except ValueError:
                pass
        return ReflectionsConfig(qdrant_host=url_part)

    # Load from config file
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return ReflectionsConfig.from_dict(data)

    # Return defaults
    return ReflectionsConfig()


def save_config(config: ReflectionsConfig) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)


def get_qdrant_url() -> str:
    """Get the Qdrant URL from config or environment."""
    return load_config().qdrant_url
