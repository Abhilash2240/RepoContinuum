"""Dual-mode Git repository validation and commit SHA resolution."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class GitResolutionResult:
    """Outcome of resolving Git metadata for a repository."""
    is_git: bool
    ref_name: str
    commit_sha: str
    warnings: List[str] = field(default_factory=list)


class GitResolver:
    """Resolves Git references and commit SHAs via CLI and pure-Python fallback."""

    HEX_SHA_REGEX = re.compile(r"^[0-9a-fA-F]{40}$")

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path.resolve()

    def resolve(self) -> GitResolutionResult:
        """Resolve current ref and commit SHA, attempting CLI first, then pure-Python."""
        warnings: List[str] = []

        # Find .git directory or file
        git_dir = self._find_git_dir(self.repo_path)
        if not git_dir:
            return GitResolutionResult(
                is_git=False,
                ref_name="unknown",
                commit_sha="0000000000000000000000000000000000000000",
                warnings=["Not a Git repository (no .git found)."],
            )

        # 1. Try Subprocess Git CLI
        cli_result = self._resolve_via_cli()
        if cli_result:
            return cli_result

        # 2. Pure-Python fallback (reading .git directly)
        warnings.append("Git CLI unavailable or restricted; used direct .git filesystem inspection.")
        py_result = self._resolve_via_filesystem(git_dir)
        return GitResolutionResult(
            is_git=py_result.is_git,
            ref_name=py_result.ref_name,
            commit_sha=py_result.commit_sha,
            warnings=warnings + py_result.warnings,
        )

    def _find_git_dir(self, start_path: Path) -> Optional[Path]:
        """Locate .git folder or file for the repository."""
        target = start_path / ".git"
        if target.is_dir():
            return target
        if target.is_file():
            # Possible git submodule / worktree with pointer
            try:
                content = target.read_text(encoding="utf-8").strip()
                if content.startswith("gitdir:"):
                    gitdir_rel = content.split(":", 1)[1].strip()
                    resolved = (start_path / gitdir_rel).resolve()
                    if resolved.is_dir():
                        return resolved
            except OSError:
                pass
        return None

    def _resolve_via_cli(self) -> Optional[GitResolutionResult]:
        """Attempt to query ref and SHA using git subprocess."""
        try:
            # Check commit SHA
            sha_proc = subprocess.run(
                ["git", "-C", str(self.repo_path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if sha_proc.returncode != 0:
                # Might be fresh repo with no commits
                if "unknown revision" in sha_proc.stderr or "fatal: ambiguous argument 'HEAD'" in sha_proc.stderr:
                    ref_proc = subprocess.run(
                        ["git", "-C", str(self.repo_path), "branch", "--show-current"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    branch = ref_proc.stdout.strip() or "main"
                    return GitResolutionResult(
                        is_git=True,
                        ref_name=branch,
                        commit_sha="0000000000000000000000000000000000000000",
                        warnings=["Repository has no commits yet."],
                    )
                return None

            commit_sha = sha_proc.stdout.strip()
            if not self.HEX_SHA_REGEX.match(commit_sha):
                return None

            # Check ref/branch name
            ref_proc = subprocess.run(
                ["git", "-C", str(self.repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            ref_name = ref_proc.stdout.strip() if ref_proc.returncode == 0 else "HEAD"

            return GitResolutionResult(
                is_git=True,
                ref_name=ref_name,
                commit_sha=commit_sha,
                warnings=[],
            )
        except (subprocess.SubprocessError, OSError, ValueError):
            return None

    def _resolve_via_filesystem(self, git_dir: Path) -> GitResolutionResult:
        """Inspect .git files directly without running subprocesses."""
        head_file = git_dir / "HEAD"
        if not head_file.exists():
            return GitResolutionResult(
                is_git=False,
                ref_name="unknown",
                commit_sha="0000000000000000000000000000000000000000",
                warnings=[".git/HEAD file not found."],
            )

        try:
            head_content = head_file.read_text(encoding="utf-8").strip()
        except OSError as e:
            return GitResolutionResult(
                is_git=False,
                ref_name="unknown",
                commit_sha="0000000000000000000000000000000000000000",
                warnings=[f"Failed to read .git/HEAD: {e}"],
            )

        # Detached HEAD (raw SHA)
        if self.HEX_SHA_REGEX.match(head_content):
            return GitResolutionResult(
                is_git=True,
                ref_name="HEAD",
                commit_sha=head_content,
            )

        # Symbolic ref: e.g. "ref: refs/heads/main"
        if head_content.startswith("ref:"):
            ref_path_str = head_content.split(":", 1)[1].strip()
            ref_name = ref_path_str.replace("refs/heads/", "")

            # 1. Look in loose refs
            loose_ref = git_dir / ref_path_str
            if loose_ref.exists():
                try:
                    sha = loose_ref.read_text(encoding="utf-8").strip()
                    if self.HEX_SHA_REGEX.match(sha):
                        return GitResolutionResult(
                            is_git=True,
                            ref_name=ref_name,
                            commit_sha=sha,
                        )
                except OSError:
                    pass

            # 2. Look in packed-refs
            packed_refs = git_dir / "packed-refs"
            if packed_refs.exists():
                try:
                    for line in packed_refs.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith(("#", "^")):
                            parts = line.split(maxsplit=1)
                            if len(parts) == 2 and parts[1] == ref_path_str:
                                if self.HEX_SHA_REGEX.match(parts[0]):
                                    return GitResolutionResult(
                                        is_git=True,
                                        ref_name=ref_name,
                                        commit_sha=parts[0],
                                    )
                except OSError:
                    pass

            # If ref file doesn't exist yet, it's a newly initialized repository
            return GitResolutionResult(
                is_git=True,
                ref_name=ref_name,
                commit_sha="0000000000000000000000000000000000000000",
                warnings=["Repository initialized with no commits yet."],
            )

        return GitResolutionResult(
            is_git=True,
            ref_name="unknown",
            commit_sha="0000000000000000000000000000000000000000",
            warnings=[f"Unrecognized .git/HEAD format: {head_content}"],
        )
