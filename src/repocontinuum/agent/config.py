"""Configuration and settings for RepoContinuum LLM agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_ENV = _PROJECT_ROOT / ".env"


class AgentSettings(BaseSettings):
    """Configuration options for the LLM provider, tool limits, and repair budgets."""

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ENV, ".env") if _PROJECT_ENV.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    llm_provider: str = Field(
        default="fake",
        validation_alias=AliasChoices("llm_provider", "AI_PROVIDER", "REPOCONTINUUM_LLM_PROVIDER", "LLM_PROVIDER"),
        description="Active LLM provider: 'gemini', 'openrouter', or 'fake'.",
    )
    gemini_api_key: Optional[SecretStr] = Field(
        default=None,
        alias="GEMINI_API_KEY",
        description="Google Gemini API key.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        alias="GEMINI_MODEL",
        description="Target Google Gemini model identifier.",
    )
    openrouter_api_key: Optional[SecretStr] = Field(
        default=None,
        alias="OPENROUTER_API_KEY",
        description="OpenRouter API key.",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
        description="OpenRouter API base URL.",
    )
    openrouter_model: str = Field(
        default="particle-ai/particle-1:free",
        alias="OPENROUTER_MODEL",
        description="Target OpenRouter model identifier.",
    )
    openrouter_site_url: Optional[str] = Field(
        default=None,
        alias="OPENROUTER_SITE_URL",
        description="Optional site URL sent via HTTP-Referer for OpenRouter rankings.",
    )
    openrouter_app_name: str = Field(
        default="RepoContinuum",
        alias="OPENROUTER_APP_NAME",
        description="Application name sent via X-Title header.",
    )
    llm_timeout_seconds: int = Field(
        default=60,
        alias="REPOCONTINUUM_LLM_TIMEOUT_SECONDS",
        description="Request timeout in seconds.",
    )
    llm_max_output_tokens: int = Field(
        default=4096,
        alias="REPOCONTINUUM_LLM_MAX_OUTPUT_TOKENS",
        description="Maximum tokens generated per response.",
    )
    llm_max_retries: int = Field(
        default=2,
        alias="REPOCONTINUUM_LLM_MAX_RETRIES",
        description="Maximum transient error retries.",
    )
    agent_max_repair_attempts: int = Field(
        default=2,
        alias="REPOCONTINUUM_AGENT_MAX_REPAIR_ATTEMPTS",
        description="Maximum autonomous verification repair loops per task.",
    )
    agent_max_tool_calls: int = Field(
        default=10,
        alias="REPOCONTINUUM_AGENT_MAX_TOOL_CALLS",
        description="Maximum tool calls allowed per task execution.",
    )
    agent_max_steps: int = Field(
        default=12,
        alias="REPOCONTINUUM_AGENT_MAX_STEPS",
        description="Maximum workflow step iterations per task.",
    )

    def is_gemini_configured(self) -> bool:
        """Check if live Gemini API key is present."""
        return self.gemini_api_key is not None and bool(self.gemini_api_key.get_secret_value().strip())

    def is_openrouter_configured(self) -> bool:
        """Check if live OpenRouter API key is present."""
        return self.openrouter_api_key is not None and bool(self.openrouter_api_key.get_secret_value().strip())
