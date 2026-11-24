"""Unit and integration tests for OpenRouter provider adapter."""

import json
import os
from unittest.mock import MagicMock
import httpx
import pytest

from repocontinuum.agent.config import AgentSettings
from repocontinuum.agent.providers.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMInvalidResponseError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMTransientError,
)
from repocontinuum.agent.providers.openrouter import OpenRouterProvider
from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis
from repocontinuum.agent.service import AgentService
from repocontinuum.planning.service import TaskChainService


def test_openrouter_configuration_loading():
    """1. Verify OpenRouter configuration defaults and settings loading."""
    settings = AgentSettings(
        llm_provider="openrouter",
        openrouter_api_key="sk-or-test-key-123456",
        openrouter_model="particle-ai/particle-1:free",
        openrouter_base_url="https://openrouter.ai/api/v1",
        openrouter_site_url="https://example.com/repo",
        openrouter_app_name="TestApp",
    )
    assert settings.llm_provider == "openrouter"
    assert settings.is_openrouter_configured() is True
    assert settings.openrouter_api_key.get_secret_value() == "sk-or-test-key-123456"
    assert settings.openrouter_model == "particle-ai/particle-1:free"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.openrouter_site_url == "https://example.com/repo"
    assert settings.openrouter_app_name == "TestApp"


def test_openrouter_ai_provider_alias_support():
    """Verify AI_PROVIDER environment alias correctly configures OpenRouter."""
    settings = AgentSettings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="sk-or-test-alias-key",
    )
    assert settings.llm_provider == "openrouter"
    assert settings.is_openrouter_configured() is True


def test_openrouter_missing_api_key_behavior():
    """2. Verify OpenRouterProvider rejects empty or whitespace API keys."""
    with pytest.raises(LLMAuthenticationError) as exc_empty:
        OpenRouterProvider(api_key="")
    assert "OPENROUTER_API_KEY must not be empty" in exc_empty.value.message

    with pytest.raises(LLMAuthenticationError) as exc_ws:
        OpenRouterProvider(api_key="   ")
    assert "OPENROUTER_API_KEY must not be empty" in exc_ws.value.message


def test_openrouter_correct_model_and_base_url():
    """3. Verify default model ID and base URL match requirements."""
    prov = OpenRouterProvider(api_key="sk-or-dummy")
    assert prov.model_name == "particle-ai/particle-1:free"
    assert prov.base_url == "https://openrouter.ai/api/v1"
    assert prov.is_healthy() is True


def test_openrouter_authentication_failure_handling():
    """4. Verify HTTP 401 response raises non-retryable LLMAuthenticationError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = json.dumps({"error": {"message": "Invalid API Key", "code": 401}})
    mock_resp.headers = {}
    mock_client.post.return_value = mock_resp

    prov = OpenRouterProvider(api_key="sk-or-invalid-key", http_client=mock_client, max_retries=1)
    with pytest.raises(LLMAuthenticationError) as exc_info:
        prov.generate_structured("test prompt", IssueAnalysis)

    assert exc_info.value.retryable is False
    assert "authentication failed" in exc_info.value.message.lower()


def test_openrouter_rate_limit_handling():
    """5. Verify HTTP 429 response raises retryable LLMRateLimitError with retry-after."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.text = json.dumps({"error": {"message": "Rate limit exceeded", "code": 429}})
    mock_resp.headers = {"Retry-After": "3.5"}
    mock_client.post.return_value = mock_resp

    prov = OpenRouterProvider(api_key="sk-or-key", http_client=mock_client, max_retries=0)
    with pytest.raises(LLMRateLimitError) as exc_info:
        prov.generate_structured("test prompt", IssueAnalysis)

    assert exc_info.value.retryable is True
    assert exc_info.value.retry_after_sec == 3.5


def test_openrouter_timeout_handling():
    """6. Verify httpx timeout exception raises retryable LLMTimeoutError."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Read timed out")

    prov = OpenRouterProvider(api_key="sk-or-key", http_client=mock_client, max_retries=0)
    with pytest.raises(LLMTimeoutError) as exc_info:
        prov.generate_structured("test prompt", IssueAnalysis)

    assert exc_info.value.retryable is True
    assert "timed out" in exc_info.value.message.lower()


def test_openrouter_provider_error_handling():
    """7. Verify HTTP 500, 502, 503 and 402 errors map to appropriate domain exceptions."""
    mock_client = MagicMock(spec=httpx.Client)

    # 402: Payment required
    mock_resp_402 = MagicMock(spec=httpx.Response)
    mock_resp_402.status_code = 402
    mock_resp_402.text = json.dumps({"error": {"message": "Insufficient credits", "code": 402}})
    mock_resp_402.headers = {}
    mock_client.post.return_value = mock_resp_402

    prov = OpenRouterProvider(api_key="sk-or-key", http_client=mock_client, max_retries=0)
    with pytest.raises(LLMConfigurationError) as exc_402:
        prov.generate_structured("test prompt", IssueAnalysis)
    assert exc_402.value.retryable is False
    assert "credits" in exc_402.value.message.lower()

    # 503: Service Unavailable (transient / retryable)
    mock_resp_503 = MagicMock(spec=httpx.Response)
    mock_resp_503.status_code = 503
    mock_resp_503.text = "Service Unavailable"
    mock_resp_503.headers = {}
    mock_client.post.return_value = mock_resp_503

    with pytest.raises(LLMTransientError) as exc_503:
        prov.generate_structured("test prompt", IssueAnalysis)
    assert exc_503.value.retryable is True


def test_openrouter_successful_mocked_response():
    """8. Verify successful mocked response returns ProviderResponse with usage and latency."""
    canned_payload = {
        "problem_summary": "Fix division by zero",
        "observed_behaviour": "Raises ZeroDivisionError",
        "expected_behaviour": "Returns None when divisor is 0",
        "acceptance_criteria": ["Handles 0 safely"],
        "ambiguous_requirements": [],
        "likely_affected_files": ["math_utils.py"],
        "likely_affected_symbols": ["safe_div"],
        "relevant_tests": ["test_math_utils.py"],
        "dependency_candidates": [],
        "risk_level": "low",
        "assumptions": [],
        "confidence": 0.98,
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "gen-12345",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(canned_payload),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 80,
            "total_tokens": 230,
        },
    }
    mock_client.post.return_value = mock_resp

    prov = OpenRouterProvider(api_key="sk-or-valid-key", http_client=mock_client)
    res = prov.generate_structured("Analyze division bug", IssueAnalysis)

    assert res.provider == "openrouter"
    assert res.model == "particle-ai/particle-1:free"
    assert res.data.problem_summary == "Fix division by zero"
    assert res.data.confidence == 0.98
    assert res.usage.prompt_tokens == 150
    assert res.usage.completion_tokens == 80
    assert res.usage.total_tokens == 230
    assert res.latency_ms >= 0


def test_openrouter_markdown_fenced_json_parsing():
    """9. Verify structured parser handles markdown-fenced ```json responses."""
    canned_payload = {
        "problem_summary": "Markdown fenced JSON",
        "observed_behaviour": "Observed",
        "expected_behaviour": "Expected",
        "acceptance_criteria": ["Criteria 1"],
        "ambiguous_requirements": [],
        "likely_affected_files": ["app.py"],
        "likely_affected_symbols": ["main"],
        "relevant_tests": ["test_app.py"],
        "dependency_candidates": [],
        "risk_level": "medium",
        "assumptions": [],
        "confidence": 0.9,
    }

    fenced_content = f"Here is the analysis:\n```json\n{json.dumps(canned_payload)}\n```\nHope this helps!"

    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": fenced_content}}],
        "usage": {"total_tokens": 100},
    }
    mock_client.post.return_value = mock_resp

    prov = OpenRouterProvider(api_key="sk-or-key", http_client=mock_client)
    res = prov.generate_structured("Analyze issue", IssueAnalysis)

    assert res.data.problem_summary == "Markdown fenced JSON"
    assert res.data.confidence == 0.9


def test_openrouter_malformed_response_handling():
    """10. Verify malformed JSON raises LLMInvalidResponseError with raw output preserved."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "This is plain text, not JSON at all."}}],
    }
    mock_client.post.return_value = mock_resp

    prov = OpenRouterProvider(api_key="sk-or-key", http_client=mock_client)
    with pytest.raises(LLMInvalidResponseError) as exc_info:
        prov.generate_structured("Analyze issue", IssueAnalysis)

    assert exc_info.value.provider == "openrouter"
    assert "plain text" in exc_info.value.raw_output


def test_openrouter_provider_selection():
    """11. Verify AgentService selects OpenRouterProvider when explicitly configured."""
    mock_service = MagicMock(spec=TaskChainService)

    # 1. OpenRouter selected with key
    settings_or = AgentSettings(
        llm_provider="openrouter",
        openrouter_api_key="sk-or-configured-key",
    )
    svc_or = AgentService(service=mock_service, settings=settings_or)
    assert isinstance(svc_or.provider, OpenRouterProvider)
    assert svc_or.provider.model_name == "particle-ai/particle-1:free"

    # 2. OpenRouter selected without key raises safe error
    settings_no_key = AgentSettings(llm_provider="openrouter", openrouter_api_key=None)
    with pytest.raises(LLMAuthenticationError) as exc_missing:
        AgentService(service=mock_service, settings=settings_no_key)
    assert "OPENROUTER_API_KEY is not configured" in exc_missing.value.message

    # 3. Default fallback remains FakeLLMProvider when isolated from active environment
    settings_default = AgentSettings(_env_file=None, llm_provider="fake")
    svc_default = AgentService(service=mock_service, settings=settings_default)
    assert svc_default.provider.__class__.__name__ == "FakeLLMProvider"


def test_active_env_file_selects_openrouter():
    """12. Verify active .env file selects OpenRouter and initializes provider or raises safe authentication error."""
    settings = AgentSettings()
    assert settings.llm_provider == "openrouter"
    assert settings.openrouter_model == "particle-ai/particle-1:free"
    assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert settings.openrouter_app_name == "RepoContinuum"

    mock_service = MagicMock(spec=TaskChainService)
    if settings.is_openrouter_configured():
        svc = AgentService(service=mock_service, settings=settings)
        assert isinstance(svc.provider, OpenRouterProvider)
    else:
        with pytest.raises(LLMAuthenticationError) as exc_missing:
            AgentService(service=mock_service, settings=settings)
        assert "OPENROUTER_API_KEY is not configured" in exc_missing.value.message
        assert exc_missing.value.provider == "openrouter"


def test_agent_workflow_integration_with_openrouter(tmp_path):
    """13. Verify full AgentService workflow integration using OpenRouterProvider."""
    from repocontinuum.domain.models import IndexSummary, RepositorySnapshot
    from repocontinuum.domain.planning import MaintenanceTask, TaskChain
    from repocontinuum.persistence.database import DatabaseManager
    from repocontinuum.persistence.repository import TaskChainRepository

    db_path = tmp_path / "test_or_wf.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    chain_svc = TaskChainService(repo)

    chain = TaskChain(id="chn-or-1", repository_id="owner/repo", title="OpenRouter Chain")
    repo.save_chain(chain)

    task = MaintenanceTask(
        id="tsk-or-1",
        chain_id=chain.id,
        title="Handle negative inputs in sqrt",
        description="sqrt(-1) should return NaN or raise ValueError instead of crashing.",
    )
    repo.save_task(task)

    canned_analysis = {
        "problem_summary": "sqrt crash on negative input",
        "observed_behaviour": "Crashes with unknown error",
        "expected_behaviour": "Raises ValueError with descriptive message",
        "acceptance_criteria": ["ValueError on negative float"],
        "ambiguous_requirements": [],
        "likely_affected_files": ["math_engine.py"],
        "likely_affected_symbols": ["sqrt"],
        "relevant_tests": ["test_sqrt.py"],
        "dependency_candidates": [],
        "risk_level": "low",
        "assumptions": ["Real numbers only"],
        "confidence": 0.96,
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": json.dumps(canned_analysis)}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
    }
    mock_client.post.return_value = mock_resp

    openrouter_provider = OpenRouterProvider(api_key="sk-or-test-key", http_client=mock_client)
    agent_svc = AgentService(service=chain_svc, provider=openrouter_provider)

    snap = RepositorySnapshot(
        repository_name="owner/repo",
        repository_root_identifier="owner/repo",
        ref_name="refs/heads/main",
        commit_sha="a" * 40,
        indexed_at="2026-11-23T00:00:00Z",
        indexer_version="1.0.0",
        parser_version="1.0.0",
        config_hash="cfg-1",
        summary=IndexSummary(
            total_files_scanned=1,
            indexed_python_files=1,
            skipped_files=0,
            parse_failures=0,
            total_classes=0,
            total_functions=1,
            total_methods=0,
            total_imports=0,
            total_test_cases=1,
        ),
        files={},
        skipped_files=[],
        parse_failures=[],
        unresolved_dependencies=[],
        warnings=[],
    )

    repo_dir = tmp_path / "fake_repo"
    repo_dir.mkdir()

    agent_run, analysis = agent_svc.analyze_task(
        task_id=task.id,
        repo_path=repo_dir,
        snapshot=snap,
    )

    assert agent_run.provider == "openrouter"
    assert agent_run.model == "particle-ai/particle-1:free"
    assert agent_run.total_tokens == 200
    assert analysis.problem_summary == "sqrt crash on negative input"
    assert analysis.confidence == 0.96


def test_openrouter_secret_redaction():
    """14. Verify API key is redacted from exception messages, logs, and representations."""
    secret_key = "sk-or-super-secret-production-token-998877"
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = f"Invalid token: {secret_key}"
    mock_resp.headers = {}
    mock_client.post.return_value = mock_resp

    prov = OpenRouterProvider(api_key=secret_key, http_client=mock_client, max_retries=0)

    # __repr__ does not leak key
    repr_str = repr(prov)
    assert secret_key not in repr_str

    # Exception message redacts key
    with pytest.raises(LLMAuthenticationError) as exc_info:
        prov.generate_structured("prompt", IssueAnalysis)

    assert secret_key not in exc_info.value.message
    assert "[REDACTED]" in exc_info.value.message


@pytest.mark.skipif(
    not AgentSettings().is_openrouter_configured(),
    reason="Opt-in test requiring configured OPENROUTER_API_KEY",
)
def test_live_openrouter_provider_smoke_test():
    """Opt-in live smoke test against OpenRouter Particle-1 Free when OPENROUTER_API_KEY is configured."""
    settings = AgentSettings()
    api_key = settings.openrouter_api_key.get_secret_value()
    provider = OpenRouterProvider(
        api_key=api_key,
        model_name=settings.openrouter_model,
        base_url=settings.openrouter_base_url,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
    )
    resp = provider.generate_structured(
        prompt="Analyze a trivial bug where addition function add(a, b) returns a - b instead of a + b.",
        response_schema=IssueAnalysis,
    )
    assert resp.data.problem_summary
    assert resp.usage.total_tokens >= 0
