"""Structured Pydantic schema for task execution planning."""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, ConfigDict, Field


class TaskPlan(BaseModel):
    """Bounded, step-by-step engineering plan for a maintenance task."""
    model_config = ConfigDict(frozen=True)

    task_id: str = Field(..., description="Target task identifier.")
    objective: str = Field(..., description="Primary engineering objective.")
    ordered_steps: List[str] = Field(..., description="Deterministic sequence of implementation steps.")
    required_predecessors: List[str] = Field(default_factory=list, description="Task IDs that must complete first.")
    affected_files: List[str] = Field(default_factory=list, description="Target files in the repository.")
    affected_symbols: List[str] = Field(default_factory=list, description="Specific classes or functions targeted.")
    test_strategy: str = Field(..., description="Verification approach and test execution strategy.")
    active_obligations: List[str] = Field(default_factory=list, description="Obligation IDs or descriptions to satisfy/preserve.")
    risks: List[str] = Field(default_factory=list, description="Potential side-effects, breaking changes, or regressions.")
    assumptions: List[str] = Field(default_factory=list, description="Working assumptions.")
    unresolved_questions: List[str] = Field(default_factory=list, description="Questions needing human attention.")
    expected_completion_conditions: List[str] = Field(default_factory=list, description="Verifiable conditions defining done.")
