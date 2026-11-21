"""Deterministic fake LLM provider for reproducible testing without API calls."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel

from repocontinuum.agent.providers.base import BaseLLMProvider, ProviderResponse, UsageMetadata
from repocontinuum.agent.providers.exceptions import (
    LLMInvalidResponseError,
    LLMProviderError,
)

T = TypeVar("T", bound=BaseModel)


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic in-memory LLM provider for unit and integration testing."""

    def __init__(
        self,
        canned_responses: Optional[Dict[Type[BaseModel], BaseModel]] = None,
        simulated_error: Optional[LLMProviderError] = None,
        healthy: bool = True,
        model_name: str = "fake-model",
    ):
        self.canned_responses = canned_responses or {}
        self.simulated_error = simulated_error
        self._healthy = healthy
        self.model_name = model_name
        self.invocations: List[Dict[str, Any]] = []

    def is_healthy(self) -> bool:
        return self._healthy

    def set_canned_response(self, schema_cls: Type[BaseModel], response: BaseModel) -> None:
        """Register a predetermined response for a given Pydantic schema."""
        self.canned_responses[schema_cls] = response

    def set_simulated_error(self, error: Optional[LLMProviderError]) -> None:
        """Set a simulated exception to be raised on the next generation call."""
        self.simulated_error = error

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: str = "",
        timeout_sec: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> ProviderResponse[T]:
        """Return a predetermined Pydantic model or raise a simulated error."""
        cid = correlation_id or f"req-fake-{uuid.uuid4().hex[:8]}"
        self.invocations.append(
            {
                "prompt": prompt,
                "response_schema": response_schema,
                "system_instruction": system_instruction,
                "timeout_sec": timeout_sec,
                "correlation_id": cid,
                "timestamp": time.time(),
            }
        )

        if self.simulated_error:
            raise self.simulated_error

        if response_schema in self.canned_responses:
            data = self.canned_responses[response_schema]
            if not isinstance(data, response_schema):
                raise LLMInvalidResponseError(
                    f"Canned response is of type {type(data).__name__}, expected {response_schema.__name__}",
                    provider="fake",
                )
            return ProviderResponse(
                data=data,  # type: ignore[arg-type]
                raw_text=data.model_dump_json(),
                usage=UsageMetadata(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                correlation_id=cid,
                model=self.model_name,
                provider="fake",
                latency_ms=10,
            )

        # Fallback: attempt to construct default instance or structured mock
        try:
            default_instance = response_schema()  # type: ignore[call-arg]
            return ProviderResponse(
                data=default_instance,
                raw_text=default_instance.model_dump_json(),
                usage=UsageMetadata(prompt_tokens=50, completion_tokens=25, total_tokens=75),
                correlation_id=cid,
                model=self.model_name,
                provider="fake",
                latency_ms=10,
            )
        except Exception:
            try:
                mock_instance = self._generate_default_instance(response_schema, prompt)
                return ProviderResponse(
                    data=mock_instance,
                    raw_text=mock_instance.model_dump_json(),
                    usage=UsageMetadata(prompt_tokens=50, completion_tokens=25, total_tokens=75),
                    correlation_id=cid,
                    model=self.model_name,
                    provider="fake",
                    latency_ms=10,
                )
            except Exception as e:
                raise LLMInvalidResponseError(
                    f"No canned response provided for schema '{response_schema.__name__}' and cannot instantiate default: {e}",
                    provider="fake",
                )

    def _generate_default_instance(self, response_schema: Type[T], prompt: str) -> T:
        """Generate a valid deterministic default model instance for testing without canned responses."""
        import re
        schema_name = response_schema.__name__

        sha_match = re.search(r"Base Commit SHA:\*{0,2}\s*([a-f0-9]{40})", prompt, re.IGNORECASE)
        if not sha_match:
            sha_match = re.search(r"\b([a-f0-9]{40})\b", prompt)
        base_sha = sha_match.group(1).strip() if sha_match else "0" * 40

        task_match = re.search(r"\(ID:\s*([^\)\s]+)\)", prompt)
        if not task_match:
            task_match = re.search(r"\b(tsk-[a-f0-9]+)\b", prompt)
        if not task_match:
            task_match = re.search(r"TASK ID:\s*([^\s\n]+)", prompt)
        task_id = task_match.group(1).strip() if task_match else "task-default" 

        if schema_name == "IssueAnalysis":
            from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis
            return IssueAnalysis(
                problem_summary="Automated analysis for issue",
                observed_behaviour="Target requires implementation or fix",
                expected_behaviour="System satisfies requirements",
                acceptance_criteria=["Verification checks pass"],
                likely_affected_files=["calc.py"],
                likely_affected_symbols=["multiply"],
                relevant_tests=["test_calc.py"],
                risk_level="low",
                confidence=0.9,
            )  # type: ignore[return-value]

        if schema_name == "TaskPlan":
            from repocontinuum.agent.schemas.task_plan import TaskPlan
            return TaskPlan(
                task_id=task_id,
                objective="Implement requested maintenance changes",
                ordered_steps=["Inspect target file", "Apply patch", "Execute verification checks"],
                affected_files=["calc.py"],
                affected_symbols=["multiply"],
                test_strategy="Run unit tests",
                expected_completion_conditions=["All tests pass cleanly"],
            )  # type: ignore[return-value]

        if schema_name == "PatchProposal":
            from repocontinuum.agent.schemas.patch_proposal import PatchProposal
            diff = (
                "--- a/calc.py\n"
                "+++ b/calc.py\n"
                "@@ -1,2 +1,5 @@\n"
                " def subtract(a, b):\n"
                "     return a - b\n"
                "+\n"
                "+def multiply(a, b):\n"
                "+    return a * b\n"
            )
            return PatchProposal(
                task_id=task_id,
                base_commit_sha=base_sha,
                summary="Implement multiply function",
                unified_diff=diff,
                changed_paths=["calc.py"],
                intended_behaviour="Add multiply function to calc.py",
                affected_obligations=[],
                verification_plan=["Run pytest"],
                assumptions=[],
                known_limitations=[],
            )  # type: ignore[return-value]

        raise ValueError(f"Unknown schema type: {schema_name}")
