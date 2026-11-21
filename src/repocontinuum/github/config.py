"""Configuration management for GitHub App read-only integration."""

from __future__ import annotations

from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """Configuration settings for GitHub App read-only integration."""

    model_config = SettingsConfigDict(
        env_prefix="REPOCONTINUUM_GITHUB_",
        env_file=".env",
        extra="ignore",
    )

    app_id: Optional[str] = Field(default=None, description="GitHub App ID")
    client_id: Optional[str] = Field(default=None, description="GitHub App Client ID")
    private_key_path: Optional[str] = Field(default=None, description="Path to RSA private key PEM file")
    private_key_content: Optional[SecretStr] = Field(default=None, description="Direct RSA private key PEM content")
    webhook_secret: Optional[SecretStr] = Field(default=None, description="Webhook HMAC-SHA256 secret")
    installation_id: Optional[str] = Field(default=None, description="GitHub App Installation ID")
    api_base_url: str = Field(default="https://api.github.com", description="GitHub REST API base URL")
    mock_mode: bool = Field(default=False, description="Force FakeGitHubClient for testing")

    def is_configured(self) -> bool:
        """Check if minimum GitHub App credentials are configured."""
        has_key = bool(self.private_key_path or self.private_key_content)
        return bool(self.app_id and has_key and self.installation_id)
