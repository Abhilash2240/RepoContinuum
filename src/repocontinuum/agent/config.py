"""Configuration and settings for RepoContinuum LLM agent."""

from __future__ import annotations

import os
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Configuration options for the LLM provider, tool limits, and repair budgets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = Field(
        default="fake",
        alias="REPOCONTINUUM_LLM_PROVIDER",
        description="Active LLM provider: 'gemini' or 'fake'.",
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
