"""Strongly-typed Pydantic schemas for GitHub API entities."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


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
