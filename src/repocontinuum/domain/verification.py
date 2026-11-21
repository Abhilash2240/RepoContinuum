"""Domain models and schemas for patch management and isolated verification."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PatchStatus(str, Enum):
    """Lifecycle status of a proposed patch."""
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    FAILED_APPLICATION = "FAILED_APPLICATION"


class CheckStatus(str, Enum):
    """Outcome status of an individual verification check."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"
    INCONCLUSIVE = "INCONCLUSIVE"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


class VerificationRunStatus(str, Enum):
    """Overall status of a verification pipeline execution."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"


class SandboxType(str, Enum):
    """Execution sandbox mechanism."""
    DOCKER = "docker"
    FAKE = "fake"


class DiffHunk(BaseModel):
    """Parsed hunk within a unified diff."""
    model_config = ConfigDict(frozen=True)

    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    lines: List[str] = Field(default_factory=list)


class FileDiff(BaseModel):
    """Parsed changes for a single file within a unified diff."""
    model_config = ConfigDict(frozen=True)

    old_path: str
    new_path: str
    is_creation: bool = False
    is_deletion: bool = False
    is_rename: bool = False
    hunks: List[DiffHunk] = Field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0


class Patch(BaseModel):
    """Immutable, validated patch bound to a repository, task, and exact base commit SHA."""
    model_config = ConfigDict(frozen=True)

    id: str
    repository_id: str
    task_id: str
    base_sha: str
    patch_hash: str
    diff_content: str
    changed_paths: List[str] = Field(default_factory=list)
    total_added_lines: int = 0
    total_removed_lines: int = 0
    status: PatchStatus = PatchStatus.PROPOSED
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class WorkspaceMetadata(BaseModel):
    """Metadata describing a temporary disposable working copy."""
    model_config = ConfigDict(frozen=True)

    workspace_id: str
    repository_id: str
    base_sha: str
    path: str
    is_disposable: bool = True
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    cleaned_up: bool = False


class VerificationCheck(BaseModel):
    """Individual verification check executed within the sandbox."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    command: List[str]
    status: CheckStatus
    exit_code: Optional[int] = None
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
    executed_in_sandbox: bool = False
    message: str = ""


class ObligationRecheckResult(BaseModel):
    """Outcome of re-verifying an earlier acceptance obligation after later changes."""
    model_config = ConfigDict(frozen=True)

    obligation_id: str
    source_task_id: str
    description: str
    verifier_ref: Optional[str]
    status: CheckStatus
    is_regression: bool = False
    message: str = ""


class VerificationRun(BaseModel):
    """Immutable record of an isolated verification execution run."""
    model_config = ConfigDict(frozen=True)

    id: str
    patch_id: str
    task_id: str
    chain_id: str
    base_sha: str
    workspace_id: str
    sandbox_type: SandboxType
    image_tag: str
    image_digest: Optional[str] = None
    started_at: str
    completed_at: str
    status: VerificationRunStatus
    checks: List[VerificationCheck] = Field(default_factory=list)
    obligation_rechecks: List[ObligationRecheckResult] = Field(default_factory=list)
    has_regressions: bool = False


class EvidenceReport(BaseModel):
    """Comprehensive, auditable evidence report combining diff, execution, and obligation checks."""
    model_config = ConfigDict(frozen=True)

    report_id: str
    repository_id: str
    chain_id: str
    task_id: str
    base_sha: str
    patch_id: str
    patch_hash: str
    changed_files: List[str]
    added_lines_count: int
    removed_lines_count: int
    workspace_id: str
    execution_image: str
    execution_image_digest: Optional[str]
    sandbox_type: SandboxType
    checks_executed: List[VerificationCheck]
    earlier_obligations_rechecked: List[ObligationRecheckResult]
    regressions_detected: List[str]
    skipped_or_unsupported_checks: List[str]
    outstanding_risks: List[str]
    verification_conclusion: CheckStatus
    summary_markdown: str
    generated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
