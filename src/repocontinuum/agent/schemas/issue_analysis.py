"""Structured Pydantic schema for LLM issue analysis."""

from __future__ import annotations

from typing import List, Literal
from pydantic import BaseModel, ConfigDict, Field


class IssueAnalysis(BaseModel):
    """Rigorous analytical breakdown of an engineering maintenance issue."""
    model_config = ConfigDict(frozen=True)

    problem_summary: str = Field(..., description="Concise synopsis of the bug, refactoring goal, or task.")
    observed_behaviour: str = Field(..., description="Current system behaviour or error state.")
    expected_behaviour: str = Field(..., description="Target system behaviour following completion.")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Concrete testable obligations.")
    ambiguous_requirements: List[str] = Field(default_factory=list, description="Unclear or unspecified details.")
    likely_affected_files: List[str] = Field(default_factory=list, description="Relative paths of repository files likely requiring modification.")
    likely_affected_symbols: List[str] = Field(default_factory=list, description="Functions, classes, or methods to be changed.")
    relevant_tests: List[str] = Field(default_factory=list, description="Existing or candidate test files/functions.")
    dependency_candidates: List[str] = Field(default_factory=list, description="Candidate predecessor task IDs or prerequisite components.")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(default="medium", description="Assessed risk level.")
    assumptions: List[str] = Field(default_factory=list, description="Explicit engineering assumptions made due to missing information.")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0.")
