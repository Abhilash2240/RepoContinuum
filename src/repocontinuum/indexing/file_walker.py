"""Filesystem traversal engine with strict security boundaries and ignore policies."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from repocontinuum.domain.models import SkippedFile, SkipReason


@dataclass(frozen=True)
class FileWalkResult:
    """Outcome of safely scanning a repository workspace."""
    python_files: List[Path] = field(default_factory=list)
    skipped_files: List[SkippedFile] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class FileWalker:
    """Safe repository file walker enforcing boundaries, ignore rules, and size limits."""

    CHUNK_SIZE_FOR_BINARY_CHECK = 8192

    def __init__(
        self,
        repo_root: Path,
        ignored_directories: Set[str],
        max_file_size_bytes: int = 1_048_576,
        include_untracked: bool = True,
    ):
        self.raw_root = repo_root
        self.repo_root = repo_root.resolve()
        self.ignored_directories = {d.lower() for d in ignored_directories}
        self.max_file_size_bytes = max_file_size_bytes
        self.include_untracked = include_untracked

    def walk(self) -> FileWalkResult:
        """Walk the repository directory tree safely."""
        if not self.repo_root.exists() or not self.repo_root.is_dir():
            raise ValueError(f"Repository path does not exist or is not a directory: {self.repo_root}")

        python_files: List[Path] = []
        skipped_files: List[SkippedFile] = []
        warnings: List[str] = []

        for root, dirs, files in os.walk(str(self.repo_root), followlinks=False):
            current_dir = Path(root)

            # 1. Prune ignored directory names in-place
            dirs[:] = [
                d for d in dirs
                if d.lower() not in self.ignored_directories
                and not self._is_symlink_escape(current_dir / d, skipped_files)
            ]

            # 2. Inspect files
            for filename in files:
                file_path = current_dir / filename
                rel_posix = self._to_relative_posix(file_path)

                # Check if symlink escapes root
                if file_path.is_symlink():
                    try:
                        target = file_path.resolve()
                        if not self._is_within_root(target):
                            skipped_files.append(
                                SkippedFile(
                                    path=rel_posix,
                                    reason=SkipReason.SYMLINK_ESCAPE,
                                    details=f"Symlink points outside repository root to: {target}",
                                )
                            )
                            continue
                    except (OSError, RuntimeError) as e:
                        skipped_files.append(
                            SkippedFile(
                                path=rel_posix,
                                reason=SkipReason.SYMLINK_ESCAPE,
                                details=f"Failed to resolve symlink: {e}",
                            )
                        )
                        continue

                # Check path containment
                try:
                    resolved_file = file_path.resolve()
                    if not self._is_within_root(resolved_file):
                        skipped_files.append(
                            SkippedFile(
                                path=rel_posix,
                                reason=SkipReason.PATH_TRAVERSAL,
                                details="File path escapes repository boundary.",
                            )
                        )
                        continue
                except (OSError, RuntimeError):
                    continue

                # Check file size
                try:
                    stat_info = file_path.stat()
                    if stat_info.st_size > self.max_file_size_bytes:
                        skipped_files.append(
                            SkippedFile(
                                path=rel_posix,
                                reason=SkipReason.OVERSIZED,
                                details=f"File size {stat_info.st_size} bytes exceeds limit {self.max_file_size_bytes} bytes",
                            )
                        )
                        continue
                except OSError as e:
                    warnings.append(f"Could not stat file {rel_posix}: {e}")
                    continue

                # Detect binary content
                if self._is_binary_file(file_path):
                    skipped_files.append(
                        SkippedFile(
                            path=rel_posix,
                            reason=SkipReason.BINARY,
                            details="Binary file detected (contains null bytes).",
                        )
                    )
                    continue

                # Check language extension
                if file_path.suffix.lower() in {".py", ".pyi"}:
                    python_files.append(file_path)
                else:
                    skipped_files.append(
                        SkippedFile(
                            path=rel_posix,
                            reason=SkipReason.UNSUPPORTED_TYPE,
                            details=f"Non-Python file extension: {file_path.suffix}",
                        )
                    )

        # Sort python files deterministically by relative POSIX path
        python_files.sort(key=lambda p: self._to_relative_posix(p))

        return FileWalkResult(
            python_files=python_files,
            skipped_files=skipped_files,
            warnings=warnings,
        )

    def _is_within_root(self, path: Path) -> bool:
        """Verify that resolved path is strictly within the repository root."""
        try:
            path.relative_to(self.repo_root)
            return True
        except ValueError:
            return False

    def _is_symlink_escape(self, dir_path: Path, skipped_records: List[SkippedFile]) -> bool:
        """Check if a directory symlink points outside repository root."""
        if dir_path.is_symlink():
            rel_posix = self._to_relative_posix(dir_path)
            try:
                target = dir_path.resolve()
                if not self._is_within_root(target):
                    skipped_records.append(
                        SkippedFile(
                            path=rel_posix,
                            reason=SkipReason.SYMLINK_ESCAPE,
                            details=f"Directory symlink points outside repository: {target}",
                        )
                    )
                    return True
            except OSError:
                return True
        return False

    def _is_binary_file(self, path: Path) -> bool:
        """Detect binary files by inspecting initial bytes for null characters."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(self.CHUNK_SIZE_FOR_BINARY_CHECK)
                return b"\0" in chunk
        except OSError:
            return False

    def _to_relative_posix(self, path: Path) -> str:
        """Convert a filesystem path to a relative POSIX string."""
        try:
            rel = path.relative_to(self.repo_root)
            return rel.as_posix()
        except ValueError:
            return path.name
