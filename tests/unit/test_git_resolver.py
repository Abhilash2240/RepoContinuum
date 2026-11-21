"""Unit tests for Git resolver and pure-Python fallback."""

from pathlib import Path
from repocontinuum.indexing.git_resolver import GitResolver


def test_git_resolver_pure_python_loose_ref(tmp_path: Path) -> None:
    """Verify ref and commit SHA resolution from loose refs."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/feature-xyz\n", encoding="utf-8")

    refs_dir = git_dir / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    fake_sha = "a" * 40
    (refs_dir / "feature-xyz").write_text(f"{fake_sha}\n", encoding="utf-8")

    resolver = GitResolver(tmp_path)
    # Test internal filesystem resolution directly to verify pure-Python fallback
    result = resolver._resolve_via_filesystem(git_dir)
    assert result.is_git is True
    assert result.ref_name == "feature-xyz"
    assert result.commit_sha == fake_sha


def test_git_resolver_packed_refs(tmp_path: Path) -> None:
    """Verify ref and commit SHA resolution from packed-refs."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/release-1.0\n", encoding="utf-8")

    fake_sha = "b" * 40
    packed_content = f"# packed-refs\n{fake_sha} refs/heads/release-1.0\n"
    (git_dir / "packed-refs").write_text(packed_content, encoding="utf-8")

    resolver = GitResolver(tmp_path)
    result = resolver._resolve_via_filesystem(git_dir)
    assert result.is_git is True
    assert result.ref_name == "release-1.0"
    assert result.commit_sha == fake_sha


def test_git_resolver_detached_head(tmp_path: Path) -> None:
    """Verify detached HEAD containing raw commit SHA."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    fake_sha = "c" * 40
    (git_dir / "HEAD").write_text(f"{fake_sha}\n", encoding="utf-8")

    resolver = GitResolver(tmp_path)
    result = resolver._resolve_via_filesystem(git_dir)
    assert result.is_git is True
    assert result.ref_name == "HEAD"
    assert result.commit_sha == fake_sha


def test_non_git_directory(tmp_path: Path) -> None:
    """Verify graceful handling when directory is not a Git repo."""
    resolver = GitResolver(tmp_path)
    result = resolver.resolve()
    assert result.is_git is False
    assert result.ref_name == "unknown"
    assert "Not a Git repository" in result.warnings[0]
