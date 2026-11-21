"""Base abstract interface and types for LLM providers."""

from __future__ import annotations

import abc
import uuid
from typing import Generic, Optional, Type, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T", bound=BaseModel)


class UsageMetadata(BaseModel):
    """Token consumption and cost metadata for an LLM generation."""
    model_config = ConfigDict(frozen=True)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: Optional[float] = None


class ProviderResponse(BaseModel, Generic[T]):
    """Structured result returned by an LLM provider adapter."""
    model_config = ConfigDict(frozen=True)

    data: T
    raw_text: str = ""
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    correlation_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    model: str = "unknown"
    provider: str = "unknown"
    latency_ms: int = 0


class BaseLLMProvider(abc.ABC):
    """Abstract interface for LLM providers supporting structured generation."""

    @abc.abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str = "",
        timeout_sec: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> ProviderResponse[T]:
        """Generate structured output adhering to a Pydantic schema."""
        pass

    @abc.abstractmethod
    def is_healthy(self) -> bool:
        """Verify provider availability and configuration."""
        pass
