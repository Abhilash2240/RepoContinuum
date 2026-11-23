"""GitHub App integration and publication package for RepoContinuum."""

from repocontinuum.github.approval import ApprovalValidationError, PublicationApprovalPolicy
from repocontinuum.github.auth import GitHubAppAuthManager
from repocontinuum.github.client import BaseGitHubClient, FakeGitHubClient, LiveGitHubClient, get_github_client
from repocontinuum.github.config import GitHubSettings
from repocontinuum.github.models import (
    ApprovalStatus,
    GitHubComment,
    GitHubInstallation,
    GitHubIssue,
    GitHubLabel,
    GitHubPullRequest,
    GitHubRepository,
    GitHubUser,
    PublicationApproval,
    PublicationRun,
    PublishedPullRequest,
)
from repocontinuum.github.publication_service import PublicationService
from repocontinuum.github.publisher import (
    BaseGitHubPublisher,
    FakeGitHubPublisher,
    GitHubBranchExistsError,
    GitHubPermissionError,
    GitHubPublicationError,
    GitHubRateLimitError,
    LiveGitHubPublisher,
)
from repocontinuum.github.sync import GitHubSyncService
from repocontinuum.github.webhook import verify_webhook_signature

__all__ = [
    "GitHubSettings",
    "GitHubAppAuthManager",
    "BaseGitHubClient",
    "FakeGitHubClient",
    "LiveGitHubClient",
    "get_github_client",
    "GitHubUser",
    "GitHubLabel",
    "GitHubRepository",
    "GitHubComment",
    "GitHubIssue",
    "GitHubPullRequest",
    "GitHubInstallation",
    "verify_webhook_signature",
    "GitHubSyncService",
    # Milestone 6 additions
    "ApprovalStatus",
    "PublicationApproval",
    "PublicationRun",
    "PublishedPullRequest",
    "BaseGitHubPublisher",
    "FakeGitHubPublisher",
    "LiveGitHubPublisher",
    "GitHubPublicationError",
    "GitHubPermissionError",
    "GitHubRateLimitError",
    "GitHubBranchExistsError",
    "PublicationApprovalPolicy",
    "ApprovalValidationError",
    "PublicationService",
]
