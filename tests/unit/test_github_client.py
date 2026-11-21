"""Unit tests for GitHub client: read-only queries and fake test double."""

import pytest
from repocontinuum.github.client import FakeGitHubClient


def test_fake_client_status():
    """Verify client status reporting."""
    client = FakeGitHubClient()
    status = client.get_status()
    assert status["configured"] is True
    assert status["mode"] == "fake"
    assert status["connected"] is True


def test_fake_client_repositories():
    """Verify repository listing and detail retrieval."""
    client = FakeGitHubClient()
    repos = client.list_repositories()
    assert len(repos) >= 1
    repo = repos[0]
    assert repo.name == "demo-repo"

    single = client.get_repository("repocontinuum-org", "demo-repo")
    assert single is not None
    assert single.full_name == "repocontinuum-org/demo-repo"

    missing = client.get_repository("repocontinuum-org", "non-existent")
    assert missing is None


def test_fake_client_issues_and_comments():
    """Verify issue and discussion retrieval."""
    client = FakeGitHubClient()
    issues = client.list_issues("repocontinuum-org", "demo-repo")
    assert len(issues) == 2
    assert issues[0].number == 42
    assert "Fix calculation precision" in issues[0].title

    issue_42 = client.get_issue("repocontinuum-org", "demo-repo", 42)
    assert issue_42 is not None
    assert issue_42.user.login == "alice-dev"

    comments = client.list_issue_comments("repocontinuum-org", "demo-repo", 42)
    assert len(comments) == 1
    assert comments[0].user.login == "charlie-qa"
    assert "reproduced this" in comments[0].body


def test_fake_client_pull_requests():
    """Verify pull request read queries."""
    client = FakeGitHubClient()
    prs = client.list_pull_requests("repocontinuum-org", "demo-repo")
    assert len(prs) == 1
    assert prs[0].number == 10
    assert prs[0].draft is True

    pr_10 = client.get_pull_request("repocontinuum-org", "demo-repo", 10)
    assert pr_10 is not None
    assert pr_10.head_ref == "fix/precision"


def test_client_has_no_write_methods():
    """Verify strict read-only guarantee: no write methods exist on BaseGitHubClient."""
    from repocontinuum.github.client import BaseGitHubClient
    prohibited_write_prefixes = ["create_", "update_", "delete_", "post_", "patch_", "put_", "merge_", "close_"]
    for attr in dir(BaseGitHubClient):
        for prefix in prohibited_write_prefixes:
            assert not attr.startswith(prefix), f"Prohibited write method detected: {attr}"
