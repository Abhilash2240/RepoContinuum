"""Structured agent schemas for issue analysis, planning, tool usage, and patches."""

from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis
from repocontinuum.agent.schemas.patch_proposal import PatchProposal
from repocontinuum.agent.schemas.task_plan import TaskPlan
from repocontinuum.agent.schemas.tool_intent import ToolIntent

__all__ = [
    "IssueAnalysis",
    "TaskPlan",
    "ToolIntent",
    "PatchProposal",
]
