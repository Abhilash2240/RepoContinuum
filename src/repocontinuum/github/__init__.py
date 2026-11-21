"""GitHub App read-only integration package for RepoContinuum."""

from repocontinuum.github.auth import GitHubAppAuthManager
from repocontinuum.github.client import BaseGitHubClient, FakeGitHubClient, LiveGitHubClient, get_github_client
from repocontinuum.github.config import GitHubSettings
from repocontinuum.github.models import (
    GitHubComment,
    GitHubInstallation,
    GitHubIssue,
    GitHubLabel,
    GitHubPullRequest,
    GitHubRepository,
    GitHubUser,
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
]
