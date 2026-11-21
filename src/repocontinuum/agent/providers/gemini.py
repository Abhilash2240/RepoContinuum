"""Google Gemini provider adapter using the official google-genai SDK."""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from repocontinuum.agent.providers.base import BaseLLMProvider, ProviderResponse, UsageMetadata
from repocontinuum.agent.providers.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMContentBlockedError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransientError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider implementing structured generation with retry resilience."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        max_output_tokens: int = 4096,
        timeout_seconds: int = 60,
        max_retries: int = 2,
    ):
        if not api_key or not api_key.strip():
            raise LLMAuthenticationError("GEMINI_API_KEY must not be empty.", provider="gemini")

        self.api_key = api_key
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        # Defer client creation to avoid import side-effects
        from google import genai
        self.client = genai.Client(api_key=self.api_key)

    def is_healthy(self) -> bool:
        """Check if Gemini client is configured with a valid key."""
        return bool(self.api_key and self.api_key.strip())

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str = "",
        timeout_sec: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> ProviderResponse[T]:
        """Execute structured generation with schema enforcement and bounded retries."""
        from google.genai import errors, types

        cid = correlation_id or f"req-gemini-{uuid.uuid4().hex[:8]}"
        timeout = timeout_sec or self.timeout_seconds

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            max_output_tokens=self.max_output_tokens,
            temperature=0.0,
            system_instruction=system_instruction or None,
        )

        attempts = 0
        last_error: Optional[Exception] = None

        while attempts <= self.max_retries:
            attempts += 1
            start_time = time.monotonic()
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                raw_text = response.text or ""
                if not raw_text.strip():
                    raise LLMInvalidResponseError("Gemini returned an empty response.", provider="gemini")

                # Parse JSON text into Pydantic schema
                try:
                    parsed_json = json.loads(raw_text)
                    data = response_schema.model_validate(parsed_json)
                except Exception as p_err:
                    raise LLMInvalidResponseError(
                        f"Failed to parse structured response against {response_schema.__name__}: {p_err}",
                        raw_output=raw_text,
                        provider="gemini",
                    )

                # Extract token usage
                usage = UsageMetadata()
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    um = response.usage_metadata
                    usage = UsageMetadata(
                        prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                        completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
                        total_tokens=getattr(um, "total_token_count", 0) or 0,
                    )

                return ProviderResponse(
                    data=data,
                    raw_text=raw_text,
                    usage=usage,
                    correlation_id=cid,
                    model=self.model_name,
                    provider="gemini",
                    latency_ms=latency_ms,
                )

            except errors.APIError as api_err:
                normalized = self._normalize_gemini_error(api_err)
                last_error = normalized
                if normalized.retryable and attempts <= self.max_retries:
                    backoff = (2 ** attempts) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Gemini request %s transient error: %s. Retrying in %.2fs (attempt %d/%d)",
                        cid, normalized.message, backoff, attempts, self.max_retries
                    )
                    time.sleep(backoff)
                    continue
                raise normalized

            except LLMInvalidResponseError:
                raise

            except Exception as ex:
                normalized = LLMTransientError(f"Unexpected error communicating with Gemini: {ex}", provider="gemini")
                last_error = normalized
                if attempts <= self.max_retries:
                    time.sleep(1.0)
                    continue
                raise normalized

        if last_error:
            raise last_error
        raise LLMTransientError("Max retries exhausted.", provider="gemini")

    def _normalize_gemini_error(self, err: Exception) -> LLMProviderError:
        """Map official google-genai errors to standard provider exceptions."""
        err_msg = str(err)
        code = getattr(err, "code", None)

        if code == 401 or "API_KEY_INVALID" in err_msg or "unauthorized" in err_msg.lower():
            return LLMAuthenticationError(f"Gemini authentication failed: {err_msg}", provider="gemini")
        if code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            return LLMRateLimitError(f"Gemini rate limit exceeded: {err_msg}", provider="gemini")
        if code == 408 or "DEADLINE_EXCEEDED" in err_msg or "timeout" in err_msg.lower():
            return LLMTimeoutError(f"Gemini request timed out: {err_msg}", provider="gemini")
        if code in (400, 404) or "INVALID_ARGUMENT" in err_msg:
            return LLMConfigurationError(f"Gemini invalid configuration or model: {err_msg}", provider="gemini")
        if "SAFETY" in err_msg or "BLOCKED" in err_msg:
            return LLMContentBlockedError(f"Gemini blocked content: {err_msg}", provider="gemini")

        return LLMTransientError(f"Gemini transient service error: {err_msg}", provider="gemini")
