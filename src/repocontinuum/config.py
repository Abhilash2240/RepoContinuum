"""Configuration management for RepoContinuum."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Set

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IndexerSettings(BaseSettings):
    """Configuration options for repository indexing."""

    model_config = SettingsConfigDict(
        env_prefix="REPOCONTINUUM_",
        env_file=".env",
        extra="ignore",
    )

    log_level: str = "INFO"
    max_file_size_bytes: int = Field(default=1_048_576, description="1MB default limit")
    include_untracked: bool = Field(default=True, description="Whether to include untracked files")
    indexer_version: str = "0.1.0"
    parser_version: str = "ast-py3.13-v1"

    # Ignored directories
    ignored_directories: Set[str] = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        ".tox",
        ".nox",
        ".idea",
        ".vscode",
    }

    # Custom ignore patterns (glob style)
    custom_ignore_patterns: list[str] = []

    def compute_config_hash(self) -> str:
        """Compute a deterministic SHA-256 hash representing this configuration."""
        data = {
            "max_file_size_bytes": self.max_file_size_bytes,
            "include_untracked": self.include_untracked,
            "indexer_version": self.indexer_version,
            "parser_version": self.parser_version,
            "ignored_directories": sorted(list(self.ignored_directories)),
            "custom_ignore_patterns": sorted(self.custom_ignore_patterns),
        }
        encoded = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
