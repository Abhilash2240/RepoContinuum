"""Disposable workspace manager for isolated patch application and testing."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Set

from repocontinuum.domain.verification import WorkspaceMetadata
from repocontinuum.indexing.git_resolver import GitResolver


class WorkspaceError(Exception):
    """Base exception for workspace management failures."""


class InvalidBaseCommitError(WorkspaceError):
    """Raised when repository commit SHA does not match expected base commit."""


class DisposableWorkspace:
    """Represents an isolated, temporary copy of a repository."""

    def __init__(self, metadata: WorkspaceMetadata):
        self.metadata = metadata
        self.path = Path(metadata.path)

    def cleanup(self) -> None:
        """Deterministically remove temporary workspace directory."""
        if self.path.exists():
            try:
                shutil.rmtree(self.path, ignore_errors=True)
            except OSError:
                pass


class DisposableWorkspaceManager:
    """Creates and manages the lifecycle of disposable repository workspaces."""

    DEFAULT_EXCLUDES: Set[str] = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
    }

    @classmethod
    def create_workspace(
        cls,
        repo_path: Path,
        expected_base_sha: str,
        repository_id: str = "default",
    ) -> DisposableWorkspace:
        """Validate base commit SHA and create an isolated temporary copy of the repository."""
        resolved_repo = repo_path.resolve()
        if not resolved_repo.exists() or not resolved_repo.is_dir():
            raise WorkspaceError(f"Repository path does not exist: '{resolved_repo}'")

        # 1. Base commit validation
        git_res = GitResolver(resolved_repo).resolve()
        # If repo is a git repo, enforce that commit_sha matches expected_base_sha
        if git_res.is_git and git_res.commit_sha != "0000000000000000000000000000000000000000":
            if expected_base_sha != git_res.commit_sha:
                raise InvalidBaseCommitError(
                    f"Base commit mismatch: repository is at '{git_res.commit_sha}', "
                    f"but patch requires base '{expected_base_sha}'."
                )

        # 2. Allocate isolated temporary directory
        ws_id = f"ws-{uuid.uuid4().hex[:12]}"
        temp_dir = Path(tempfile.mkdtemp(prefix=f"repocontinuum_{ws_id}_"))

        # 3. Copy repository files, excluding sensitive/ignored paths
        try:
            cls._copy_repository_tree(resolved_repo, temp_dir)
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise WorkspaceError(f"Failed to populate disposable workspace: {e}")

        metadata = WorkspaceMetadata(
            workspace_id=ws_id,
            repository_id=repository_id,
            base_sha=expected_base_sha,
            path=str(temp_dir),
            is_disposable=True,
            cleaned_up=False,
        )

        return DisposableWorkspace(metadata)

    @classmethod
    @contextmanager
    def managed_workspace(
        cls,
        repo_path: Path,
        expected_base_sha: str,
        repository_id: str = "default",
    ) -> Generator[DisposableWorkspace, None, None]:
        """Context manager creating a workspace and ensuring deterministic cleanup upon exit."""
        workspace = cls.create_workspace(repo_path, expected_base_sha, repository_id)
        try:
            yield workspace
        finally:
            workspace.cleanup()

    @classmethod
    def _copy_repository_tree(cls, source: Path, destination: Path) -> None:
        """Copy files recursively while strictly excluding .git and credentials."""
        for root, dirs, files in os.walk(str(source)):
            current_src = Path(root)
            rel_path = current_src.relative_to(source)
            current_dest = destination / rel_path

            # Prune excluded directories
            dirs[:] = [d for d in dirs if d.lower() not in cls.DEFAULT_EXCLUDES]

            current_dest.mkdir(parents=True, exist_ok=True)

            for f in files:
                # Do not copy .env or credentials
                if f.lower().startswith(".env") or f.lower() in {"id_rsa", "id_ed25519", "credentials"}:
                    continue
                src_file = current_src / f
                dest_file = current_dest / f
                try:
                    shutil.copy2(src_file, dest_file)
                except OSError:
                    pass
