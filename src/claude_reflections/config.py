"""Configuration management for claude-reflections."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def get_state_base_dir() -> Path:
    """Get the base directory for reflections state files."""
    base_dir = os.environ.get(
        "REFLECTIONS_STATE_DIR",
        os.path.expanduser("~/.claude/reflections"),
    )
    return Path(base_dir)


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_state_base_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Load configuration from file."""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def is_legacy_qdrant_config(config: dict[str, Any]) -> bool:
    """Check if config is from an old Qdrant-based install."""
    return "qdrant_port" in config
