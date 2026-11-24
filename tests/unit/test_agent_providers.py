"""Unit tests for LLM provider abstraction, fake provider, and Gemini adapter."""

import os
from unittest.mock import MagicMock, patch
import pytest

from repocontinuum.agent.providers.base import ProviderResponse, UsageMetadata
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
from repocontinuum.agent.providers.fake import FakeLLMProvider
from repocontinuum.agent.providers.gemini import GeminiProvider
from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis


def test_fake_provider_contract_and_invocation_recording():
    """Verify FakeLLMProvider records calls and returns canned structured models."""
    fake_provider = FakeLLMProvider(model_name="test-fake")
    assert fake_provider.is_healthy()

    canned = IssueAnalysis(
        problem_summary="Fix arithmetic error",
        observed_behaviour="Returns 4 instead of 5",
        expected_behaviour="Returns 5",
        acceptance_criteria=["Must pass unit test"],
        ambiguous_requirements=[],
        likely_affected_files=["calc.py"],
        likely_affected_symbols=["add"],
        relevant_tests=["test_calc.py"],
        dependency_candidates=[],
        risk_level="low",
        assumptions=["Standard integer math"],
        confidence=0.95,
    )
    fake_provider.set_canned_response(IssueAnalysis, canned)

    resp = fake_provider.generate_structured(
        prompt="Analyze the issue in calc.py",
        response_schema=IssueAnalysis,
        system_instruction="Be concise",
        correlation_id="test-cid-123",
    )

    assert resp.provider == "fake"
    assert resp.model == "test-fake"
    assert resp.correlation_id == "test-cid-123"
    assert resp.data.problem_summary == "Fix arithmetic error"
    assert resp.data.confidence == 0.95
    assert len(fake_provider.invocations) == 1
    assert fake_provider.invocations[0]["prompt"] == "Analyze the issue in calc.py"


def test_fake_provider_simulated_errors():
    """Verify FakeLLMProvider accurately simulates provider error conditions."""
    fake = FakeLLMProvider()

    # Rate limit error
    fake.set_simulated_error(LLMRateLimitError("Quota exceeded", retry_after_sec=5.0, provider="fake"))
    with pytest.raises(LLMRateLimitError) as exc_info:
        fake.generate_structured("prompt", IssueAnalysis)
    assert exc_info.value.retryable is True
    assert exc_info.value.retry_after_sec == 5.0

    # Timeout error
    fake.set_simulated_error(LLMTimeoutError("Request deadline exceeded", provider="fake"))
    with pytest.raises(LLMTimeoutError) as exc_timeout:
        fake.generate_structured("prompt", IssueAnalysis)
    assert exc_timeout.value.retryable is True

    # Authentication error
    fake.set_simulated_error(LLMAuthenticationError("Invalid API key", provider="fake"))
    with pytest.raises(LLMAuthenticationError) as exc_auth:
        fake.generate_structured("prompt", IssueAnalysis)
    assert exc_auth.value.retryable is False


def test_gemini_provider_requires_api_key():
    """Verify GeminiProvider rejects empty or whitespace API keys."""
    with pytest.raises(LLMAuthenticationError):
        GeminiProvider(api_key="")
    with pytest.raises(LLMAuthenticationError):
        GeminiProvider(api_key="   ")


def test_gemini_provider_error_normalization():
    """Verify error normalizer maps Google GenAI API errors to standard domain exceptions."""
    pytest.importorskip("google.genai")
    with patch("google.genai.Client"):
        prov = GeminiProvider(api_key="test-dummy-key")

        # Mock APIError with code 401
        err_401 = Exception("API_KEY_INVALID: User not authorized")
        setattr(err_401, "code", 401)
        norm_401 = prov._normalize_gemini_error(err_401)
        assert isinstance(norm_401, LLMAuthenticationError)
        assert norm_401.retryable is False

        # Mock APIError with code 429
        err_429 = Exception("RESOURCE_EXHAUSTED: Rate limit exceeded")
        setattr(err_429, "code", 429)
        norm_429 = prov._normalize_gemini_error(err_429)
        assert isinstance(norm_429, LLMRateLimitError)
        assert norm_429.retryable is True

        # Mock APIError with code 408
        err_408 = Exception("DEADLINE_EXCEEDED")
        setattr(err_408, "code", 408)
        norm_408 = prov._normalize_gemini_error(err_408)
        assert isinstance(norm_408, LLMTimeoutError)
        assert norm_408.retryable is True

        # Safety blocked
        err_safety = Exception("SAFETY: Generation blocked by safety filter")
        norm_safety = prov._normalize_gemini_error(err_safety)
        assert isinstance(norm_safety, LLMContentBlockedError)


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="Opt-in test requiring live GEMINI_API_KEY")
def test_live_gemini_provider_smoke_test():
    """Opt-in smoke test against real Gemini API when GEMINI_API_KEY is supplied."""
    api_key = os.environ["GEMINI_API_KEY"]
    provider = GeminiProvider(api_key=api_key, model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    resp = provider.generate_structured(
        prompt="Analyze a trivial bug where addition function add(a, b) returns a - b instead of a + b.",
        response_schema=IssueAnalysis,
    )
    assert resp.data.problem_summary
    assert resp.usage.total_tokens > 0
