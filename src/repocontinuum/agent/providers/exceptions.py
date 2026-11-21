"""Provider-independent error hierarchy for LLM interactions."""

from __future__ import annotations


class LLMProviderError(Exception):
    """Base exception for all LLM provider errors."""

    def __init__(self, message: str, retryable: bool = False, provider: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.provider = provider


class LLMAuthenticationError(LLMProviderError):
    """Raised when provider credentials or API keys are invalid or missing."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message=message, retryable=False, provider=provider)


class LLMConfigurationError(LLMProviderError):
    """Raised when model configuration or parameters are invalid."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message=message, retryable=False, provider=provider)


class LLMRateLimitError(LLMProviderError):
    """Raised when provider quota or rate limits are exceeded."""

    def __init__(self, message: str, retry_after_sec: float = 2.0, provider: str = "unknown"):
        super().__init__(message=message, retryable=True, provider=provider)
        self.retry_after_sec = retry_after_sec


class LLMTimeoutError(LLMProviderError):
    """Raised when a request to the LLM exceeds the configured timeout."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message=message, retryable=True, provider=provider)


class LLMTransientError(LLMProviderError):
    """Raised when a 5xx or transient backend error occurs."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message=message, retryable=True, provider=provider)


class LLMContentBlockedError(LLMProviderError):
    """Raised when prompt or response is blocked by safety filters."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message=message, retryable=False, provider=provider)


class LLMInvalidResponseError(LLMProviderError):
    """Raised when response does not conform to the expected Pydantic schema."""

    def __init__(self, message: str, raw_output: str = "", provider: str = "unknown"):
        super().__init__(message=message, retryable=False, provider=provider)
        self.raw_output = raw_output
