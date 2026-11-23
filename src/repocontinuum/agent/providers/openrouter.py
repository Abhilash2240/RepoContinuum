"""OpenRouter provider adapter implementing structured generation via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from typing import Optional, Type, TypeVar
import httpx
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


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter provider using the OpenAI-compatible Chat Completions API with Particle-1 Free."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "particle-ai/particle-1:free",
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: Optional[str] = None,
        app_name: str = "RepoContinuum",
        max_output_tokens: int = 4096,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ):
        if not api_key or not api_key.strip():
            raise LLMAuthenticationError("OPENROUTER_API_KEY must not be empty.", provider="openrouter")

        self.api_key = api_key.strip()
        self.model_name = model_name or "particle-ai/particle-1:free"
        self.base_url = (base_url or "https://openrouter.ai/api/v1").rstrip("/")
        self.site_url = site_url
        self.app_name = app_name or "RepoContinuum"
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = http_client

    def __repr__(self) -> str:
        # Crucial: Never expose API key in string representations
        return (
            f"OpenRouterProvider(model_name={self.model_name!r}, "
            f"base_url={self.base_url!r}, app_name={self.app_name!r})"
        )

    def is_healthy(self) -> bool:
        """Verify provider availability and configuration."""
        return bool(self.api_key and self.api_key.strip() and self.base_url)

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str = "",
        timeout_sec: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> ProviderResponse[T]:
        """Execute structured generation using OpenAI-compatible Chat Completions API with schema enforcement."""
        cid = correlation_id or f"req-openrouter-{uuid.uuid4().hex[:8]}"
        timeout = timeout_sec or self.timeout_seconds

        # Construct structured format instructions
        schema_dict = response_schema.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2)
        format_directive = (
            f"You must return ONLY a single, valid JSON object adhering strictly to the following JSON schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any prose, markdown explanation, conversational text, or backticks outside the JSON."
        )

        full_system = f"{system_instruction.strip()}\n\n{format_directive}".strip() if system_instruction else format_directive

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ]

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_output_tokens,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        attempts = 0
        last_error: Optional[Exception] = None

        while attempts <= self.max_retries:
            attempts += 1
            start_time = time.monotonic()
            try:
                raw_text, usage_data = self._execute_request(
                    endpoint=endpoint,
                    headers=headers,
                    payload=payload,
                    timeout=timeout,
                    cid=cid,
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                if not raw_text or not raw_text.strip():
                    raise LLMInvalidResponseError("OpenRouter returned an empty response.", provider="openrouter")

                # Parse JSON text into Pydantic schema
                cleaned_text = self._extract_clean_json(raw_text)
                try:
                    parsed_json = json.loads(cleaned_text)
                    data = response_schema.model_validate(parsed_json)
                except Exception as p_err:
                    raise LLMInvalidResponseError(
                        f"Failed to parse structured response against {response_schema.__name__}: {self._redact_secrets(str(p_err))}",
                        raw_output=self._redact_secrets(raw_text),
                        provider="openrouter",
                    )

                usage = UsageMetadata(
                    prompt_tokens=usage_data.get("prompt_tokens", 0) or 0,
                    completion_tokens=usage_data.get("completion_tokens", 0) or 0,
                    total_tokens=usage_data.get("total_tokens", 0) or 0,
                )

                return ProviderResponse(
                    data=data,
                    raw_text=raw_text,
                    usage=usage,
                    correlation_id=cid,
                    model=self.model_name,
                    provider="openrouter",
                    latency_ms=latency_ms,
                )

            except LLMInvalidResponseError:
                # Schema/validation errors are not retryable
                raise

            except LLMProviderError as prov_err:
                last_error = prov_err
                if prov_err.retryable and attempts <= self.max_retries:
                    retry_after = getattr(prov_err, "retry_after_sec", None)
                    backoff = retry_after if retry_after else (2 ** attempts) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "OpenRouter request %s transient error: %s. Retrying in %.2fs (attempt %d/%d)",
                        cid, prov_err.message, backoff, attempts, self.max_retries
                    )
                    time.sleep(backoff)
                    continue
                raise

            except Exception as ex:
                safe_msg = self._redact_secrets(str(ex))
                normalized = LLMTransientError(
                    f"Unexpected error communicating with OpenRouter: {safe_msg}",
                    provider="openrouter",
                )
                last_error = normalized
                if attempts <= self.max_retries:
                    time.sleep(1.0)
                    continue
                raise normalized

        if last_error:
            raise last_error
        raise LLMTransientError("Max retries exhausted.", provider="openrouter")

    def _execute_request(
        self,
        endpoint: str,
        headers: dict,
        payload: dict,
        timeout: float,
        cid: str,
    ) -> tuple[str, dict]:
        """Send HTTP POST to OpenRouter chat completions endpoint and handle HTTP status codes."""
        try:
            if self._client is not None:
                resp = self._client.post(endpoint, headers=headers, json=payload, timeout=timeout)
            else:
                with httpx.Client(timeout=timeout) as client:
                    resp = client.post(endpoint, headers=headers, json=payload)
        except httpx.TimeoutException as tex:
            raise LLMTimeoutError(
                f"OpenRouter request timed out after {timeout}s: {self._redact_secrets(str(tex))}",
                provider="openrouter",
            )
        except httpx.NetworkError as nex:
            raise LLMTransientError(
                f"OpenRouter network connection error: {self._redact_secrets(str(nex))}",
                provider="openrouter",
            )

        status = resp.status_code
        if status == 200:
            try:
                res_json = resp.json()
            except Exception as jerr:
                raise LLMInvalidResponseError(
                    f"OpenRouter returned invalid HTTP JSON response: {jerr}",
                    raw_output=resp.text,
                    provider="openrouter",
                )

            choices = res_json.get("choices", [])
            if not choices:
                raise LLMInvalidResponseError(
                    "OpenRouter response contained no choices.",
                    raw_output=resp.text,
                    provider="openrouter",
                )

            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            usage = res_json.get("usage", {})
            return content, usage

        # Non-200 HTTP response mapping
        raw_body = self._redact_secrets(resp.text)
        retry_after_hdr = resp.headers.get("Retry-After")
        retry_after_val = 2.0
        if retry_after_hdr:
            try:
                retry_after_val = float(retry_after_hdr)
            except ValueError:
                pass

        if status == 401:
            raise LLMAuthenticationError(
                f"OpenRouter authentication failed (HTTP 401): {raw_body}",
                provider="openrouter",
            )
        if status == 402:
            raise LLMConfigurationError(
                f"OpenRouter payment or credits required (HTTP 402): {raw_body}",
                provider="openrouter",
            )
        if status == 429:
            raise LLMRateLimitError(
                f"OpenRouter rate limit or quota exceeded (HTTP 429): {raw_body}",
                retry_after_sec=retry_after_val,
                provider="openrouter",
            )
        if status in (400, 404):
            lower_body = raw_body.lower()
            if "context_length" in lower_body or "maximum context length" in lower_body or "too long" in lower_body:
                raise LLMConfigurationError(
                    f"OpenRouter context length exceeded (HTTP {status}): {raw_body}",
                    provider="openrouter",
                )
            if "response_format" in lower_body and "response_format" in payload:
                # Model doesn't support response_format; retry without response_format
                payload_fallback = dict(payload)
                payload_fallback.pop("response_format", None)
                return self._execute_request(endpoint, headers, payload_fallback, timeout, cid)
            raise LLMConfigurationError(
                f"OpenRouter invalid request or model configuration (HTTP {status}): {raw_body}",
                provider="openrouter",
            )
        if status in (500, 502, 503, 504):
            raise LLMTransientError(
                f"OpenRouter upstream service error (HTTP {status}): {raw_body}",
                provider="openrouter",
            )

        raise LLMTransientError(
            f"OpenRouter unexpected HTTP status {status}: {raw_body}",
            provider="openrouter",
        )

    def _extract_clean_json(self, text: str) -> str:
        """Clean markdown code fences and extraneous whitespace from model response."""
        stripped = text.strip()
        # Handle ```json ... ``` code fences
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()

        # If there is extraneous text before/after JSON, extract from first { to last }
        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            stripped = stripped[first_brace : last_brace + 1]

        return stripped

    def _redact_secrets(self, text: str) -> str:
        """Guarantee API keys never appear in error messages, logs, or traces."""
        if not text or not self.api_key:
            return text
        return text.replace(self.api_key, "[REDACTED]")
