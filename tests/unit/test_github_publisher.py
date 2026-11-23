"""Unit tests for GitHub write publisher interface and error handling."""

import pytest
from repocontinuum.github.models import GitHubPullRequest
from repocontinuum.github.publisher import (
    BaseGitHubPublisher,
    FakeGitHubPublisher,
    GitHubBranchExistsError,
    GitHubPermissionError,
    GitHubPublicationError,
    GitHubRateLimitError,
)


def test_publisher_interface_excludes_prohibited_methods():
    """Verify that BaseGitHubPublisher strictly excludes merge, delete, and admin methods."""
    prohibited_names = [
        "merge",
        "merge_pull_request",
        "delete_branch",
        "delete_ref",
        "force_push",
        "modify_settings",
        "auto_merge",
        "deploy",
    ]
    for name in prohibited_names:
        assert not hasattr(BaseGitHubPublisher, name), f"Prohibited method '{name}' found on BaseGitHubPublisher"


def test_fake_publisher_branch_creation():
    """Test branch creation at exact base commit SHA."""
    publisher = FakeGitHubPublisher()
    ref = publisher.create_branch("octocat", "Hello-World", "repocontinuum/task-1-abc", "a" * 40)
    assert ref == "refs/heads/repocontinuum/task-1-abc"
    assert publisher.branches["octocat/Hello-World:repocontinuum/task-1-abc"] == "a" * 40

    # Duplicate branch creation raises GitHubBranchExistsError
    with pytest.raises(GitHubBranchExistsError, match="already exists"):
        publisher.create_branch("octocat", "Hello-World", "repocontinuum/task-1-abc", "a" * 40)


def test_fake_publisher_publish_commit():
    """Test publishing a commit with patch content."""
    publisher = FakeGitHubPublisher()
    publisher.create_branch("octocat", "Hello-World", "feat-branch", "a" * 40)

    patch_text = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n"
    head_sha = publisher.publish_commit(
        owner="octocat",
        repo="Hello-World",
        branch_name="feat-branch",
        patch_content=patch_text,
        commit_message="feat: apply approved patch",
        base_commit_sha="a" * 40,
    )
    assert len(head_sha) == 40
    assert publisher.branches["octocat/Hello-World:feat-branch"] == head_sha
    assert len(publisher.commits) == 1


def test_fake_publisher_create_pull_request_and_idempotency():
    """Test PR creation and idempotent retrieval."""
    publisher = FakeGitHubPublisher()
    publisher.create_branch("octocat", "Hello-World", "feat-branch", "a" * 40)

    pr1 = publisher.create_pull_request(
        owner="octocat",
        repo="Hello-World",
        title="[RepoContinuum] Update feature",
        body="Automated maintenance PR",
        head_branch="feat-branch",
        base_branch="main",
    )
    assert pr1.number == 101
    assert pr1.title == "[RepoContinuum] Update feature"
    assert pr1.head_ref == "feat-branch"
    assert pr1.base_ref == "main"

    # Idempotent re-creation returns the identical PR
    pr2 = publisher.create_pull_request(
        owner="octocat",
        repo="Hello-World",
        title="[RepoContinuum] Update feature",
        body="Automated maintenance PR",
        head_branch="feat-branch",
        base_branch="main",
    )
    assert pr2.number == pr1.number
    assert pr2.id == pr1.id


def test_fake_publisher_error_handling():
    """Test simulated permission denial, rate limit, and timeout."""
    publisher = FakeGitHubPublisher()

    # Permission denial
    publisher.simulate_permission_denied = True
    with pytest.raises(GitHubPermissionError, match="Contents write required"):
        publisher.create_branch("octocat", "Hello-World", "test-b", "0" * 40)
    publisher.simulate_permission_denied = False

    # Rate limit
    publisher.simulate_rate_limit = True
    with pytest.raises(GitHubRateLimitError, match="rate limit exceeded"):
        publisher.create_branch("octocat", "Hello-World", "test-b", "0" * 40)
    publisher.simulate_rate_limit = False

    # Network timeout
    publisher.simulate_network_timeout = True
    with pytest.raises(GitHubPublicationError, match="timed out"):
        publisher.create_branch("octocat", "Hello-World", "test-b", "0" * 40)
