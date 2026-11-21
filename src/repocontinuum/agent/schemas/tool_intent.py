"""Structured Pydantic schema for requesting a controlled tool invocation."""

from __future__ import annotations

from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class ToolIntent(BaseModel):
    """Model request to invoke a bounded application read tool."""
    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(..., description="Name of the permitted tool.")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool.")
    purpose: str = Field(..., description="Why this information is needed for the task.")
    expected_result: str = Field(..., description="What the agent expects to discover.")
