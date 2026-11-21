"""Structured Pydantic schema for proposing code patches."""

from __future__ import annotations

from typing import List
from pydantic import BaseModel, ConfigDict, Field


class PatchProposal(BaseModel):
    """Structured patch proposal with explanation, assumptions, and unified diff."""
    model_config = ConfigDict(frozen=True)

    task_id: str = Field(..., description="Target task identifier.")
    base_commit_sha: str = Field(..., description="Base commit SHA the patch is crafted against.")
    summary: str = Field(..., description="Technical summary of proposed changes.")
    unified_diff: str = Field(..., description="Complete unified diff (diff -u format).")
    changed_paths: List[str] = Field(default_factory=list, description="Relative paths of files modified, added, or deleted.")
    intended_behaviour: str = Field(..., description="Functional behavior introduced or corrected.")
    affected_obligations: List[str] = Field(default_factory=list, description="Obligations addressed or impacted.")
    verification_plan: List[str] = Field(default_factory=list, description="Verification checks to execute.")
    assumptions: List[str] = Field(default_factory=list, description="Key assumptions underlying the patch.")
    known_limitations: List[str] = Field(default_factory=list, description="Scope boundaries and limitations.")
