"""Strongly-typed Pydantic schemas for GitHub API entities and publication workflows."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    """Lifecycle status for publication approvals and runs."""
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    INVALIDATED = "INVALIDATED"
    PUBLISHING = "PUBLISHING"
    BRANCH_CREATED = "BRANCH_CREATED"
    PR_CREATED = "PR_CREATED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GitHubUser(BaseModel):
    """GitHub user or bot account."""
    model_config = ConfigDict(frozen=True)

    login: str
    id: int
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None


class GitHubLabel(BaseModel):
    """GitHub issue or PR label."""
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    color: str
    description: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub repository representation."""
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    full_name: str
    owner: str
    private: bool
    description: Optional[str] = None
    html_url: str
    default_branch: str = "main"
    open_issues_count: int = 0


class GitHubComment(BaseModel):
    """GitHub issue or pull request comment."""
    model_config = ConfigDict(frozen=True)

    id: int
    body: str
    user: Optional[GitHubUser] = None
    html_url: str
    created_at: str
    updated_at: str


class GitHubIssue(BaseModel):
    """GitHub issue representation."""
    model_config = ConfigDict(frozen=True)

    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str = "open"
    html_url: str
    user: Optional[GitHubUser] = None
    labels: List[GitHubLabel] = Field(default_factory=list)
    comments_count: int = 0
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None


class GitHubPullRequest(BaseModel):
    """GitHub pull request representation."""
    model_config = ConfigDict(frozen=True)

    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str = "open"
    html_url: str
    user: Optional[GitHubUser] = None
    head_ref: str
    head_sha: str
    base_ref: str
    base_sha: str
    draft: bool = False
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    merged_at: Optional[str] = None


class GitHubInstallation(BaseModel):
    """GitHub App installation metadata."""
    model_config = ConfigDict(frozen=True)

    id: int
    account_login: str
    account_type: str = "User"
    repository_selection: str = "selected"
    permissions: dict = Field(default_factory=dict)


class PublicationApproval(BaseModel):
    """Immutable record of human authorization bound to an exact patch and target."""
    model_config = ConfigDict(frozen=False)

    id: str
    repository_owner: str
    repository_name: str
    repository_id: str
    task_id: str
    chain_id: str
    patch_id: str
    patch_hash: str
    base_commit_sha: str
    target_base_branch: str
    proposed_head_branch: str
    verification_report_id: str
    verification_run_id: str
    approver_identity: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.AWAITING_APPROVAL
    invalidation_reason: Optional[str] = None
    created_at: str
    approved_at: Optional[str] = None
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicationRun(BaseModel):
    """Execution telemetry for a patch publication workflow."""
    model_config = ConfigDict(frozen=False)

    id: str
    approval_id: str
    task_id: str
    chain_id: str
    repository_owner: str
    repository_name: str
    head_branch: str
    base_branch: str
    base_commit_sha: str
    head_commit_sha: Optional[str] = None
    pull_request_number: Optional[int] = None
    pull_request_url: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.PUBLISHING
    attempt_count: int = 1
    error_message: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


class PublishedPullRequest(BaseModel):
    """Persisted outcome of an approved PR publication."""
    model_config = ConfigDict(frozen=True)

    id: str
    run_id: str
    approval_id: str
    repository_owner: str
    repository_name: str
    pr_number: int
    html_url: str
    title: str
    body: str
    head_branch: str
    base_branch: str
    head_sha: str
    base_sha: str
    created_at: str
