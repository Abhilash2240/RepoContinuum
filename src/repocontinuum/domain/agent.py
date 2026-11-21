"""Domain data models for bounded LLM agent execution, observability, and auditing."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AgentRunStatus(str, Enum):
    """Lifecycle status of an agent execution run."""
    PENDING = "PENDING"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    PLAN_PROPOSED = "PLAN_PROPOSED"
    PLAN_APPROVED = "PLAN_APPROVED"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_PASSED = "VERIFICATION_PASSED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRun(BaseModel):
    """Durable record of an LLM agent execution run."""
    model_config = ConfigDict(frozen=True)

    id: str
    chain_id: str
    task_id: str
    provider: str
    model: str
    status: AgentRunStatus = AgentRunStatus.PENDING
    prompt_hash: str = ""
    prompt_version: str = "1.0"
    attempt_number: int = 1
    max_repair_attempts: int = 2
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: Optional[float] = None
    latency_ms: int = 0
    retry_count: int = 0
    failure_category: Optional[str] = None
    proposed_patch_id: Optional[str] = None
    proposed_patch_hash: Optional[str] = None
    verification_run_id: Optional[str] = None
    plan_approved_by: Optional[str] = None
    plan_approved_at: Optional[str] = None
    issue_analysis_json: Optional[Dict[str, Any]] = None
    task_plan_json: Optional[Dict[str, Any]] = None
    patch_proposal_json: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    completed_at: Optional[str] = None
