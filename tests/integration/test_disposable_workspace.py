"""Integration tests for disposable workspace management and base SHA binding."""

from pathlib import Path
import pytest
from repocontinuum.execution.workspace import (
    DisposableWorkspaceManager,
    InvalidBaseCommitError,
)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a controlled fixture git repository."""
    repo = tmp_path / "original_repo"
    repo.mkdir()

    # Git metadata fixture
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    heads = git_dir / "refs" / "heads"
    heads.mkdir(parents=True)
    fake_sha = "abcdef1234567890abcdef1234567890abcdef12"
    (heads / "main").write_text(f"{fake_sha}\n", encoding="utf-8")

    # Source files
    (repo / "app.py").write_text("def run():\n    return 'original'\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET_KEY=original_secret\n", encoding="utf-8")

    return repo, fake_sha


def test_disposable_workspace_preserves_original_tree(fixture_repo: tuple[Path, str]) -> None:
    """CRITICAL: Ensure the original worktree is completely untouched when modifying workspace."""
    repo, base_sha = fixture_repo
    original_app_content = (repo / "app.py").read_text(encoding="utf-8")

    with DisposableWorkspaceManager.managed_workspace(repo, expected_base_sha=base_sha) as ws:
        assert ws.path.exists()
        assert ws.path != repo

        # Modify file inside disposable copy
        ws_app = ws.path / "app.py"
        ws_app.write_text("def run():\n    return 'modified_in_sandbox'\n", encoding="utf-8")
        assert "modified_in_sandbox" in ws_app.read_text(encoding="utf-8")

        # Original file MUST remain unchanged
        assert (repo / "app.py").read_text(encoding="utf-8") == original_app_content

        # .git and .env must NOT be present in disposable workspace
        assert not (ws.path / ".git").exists()
        assert not (ws.path / ".env").exists()

    # Workspace directory was cleaned up after exiting context
    assert not ws.path.exists()


def test_invalid_base_commit_rejected(fixture_repo: tuple[Path, str]) -> None:
    """Verify that requesting a workspace with an unexpected base commit SHA raises an error."""
    repo, _ = fixture_repo
    stale_sha = "9999999999999999999999999999999999999999"

    with pytest.raises(InvalidBaseCommitError, match="Base commit mismatch"):
        DisposableWorkspaceManager.create_workspace(repo, expected_base_sha=stale_sha)
