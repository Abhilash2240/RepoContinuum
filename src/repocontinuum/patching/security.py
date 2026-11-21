"""Security rules enforcing path boundaries, protected files, and traversal guards for patches."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Set
from repocontinuum.domain.verification import FileDiff


class PathSecurityError(Exception):
    """Raised when patch contains unsafe, escaping, or protected paths."""


class PatchSecurityValidator:
    """Validates unified diff paths against security boundaries and protected file rules."""

    # Disallowed protected path prefixes and file names
    PROTECTED_EXACT_NAMES: Set[str] = {
        ".git",
        ".env",
        ".env.local",
        ".env.production",
        ".env.staging",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "secrets.json",
        "secrets.yaml",
        "SECURITY.md",
    }

    PROTECTED_EXTENSIONS: Set[str] = {
        ".pem",
        ".key",
        ".pkcs12",
        ".pfx",
    }

    WINDOWS_DRIVE_REGEX = re.compile(r"^[a-zA-Z]:")

    @classmethod
    def validate_patch_security(
        cls,
        file_diffs: List[FileDiff],
        workspace_root: Path | None = None,
    ) -> List[str]:
        """Validate all paths modified by diffs against traversal, absolute paths, and protection rules.

        Returns list of normalized changed POSIX paths if safe.
        """
        seen_targets: Set[str] = set()
        changed_paths: List[str] = []

        for diff in file_diffs:
            # Check both old and new paths unless /dev/null
            paths_to_check = []
            if not diff.is_creation and diff.old_path != "/dev/null":
                paths_to_check.append(diff.old_path)
            if not diff.is_deletion and diff.new_path != "/dev/null":
                paths_to_check.append(diff.new_path)

            for raw_path in paths_to_check:
                cls._validate_single_path(raw_path)

            target = diff.new_path if not diff.is_deletion else diff.old_path
            norm_target = target.replace("\\", "/").strip()

            if norm_target in seen_targets:
                raise PathSecurityError(f"Duplicate target path in patch: '{norm_target}'")
            seen_targets.add(norm_target)
            changed_paths.append(norm_target)

            # If workspace root is provided, perform deep containment and symlink escape checks
            if workspace_root:
                resolved_root = workspace_root.resolve()
                target_file = (workspace_root / norm_target).resolve()
                try:
                    target_file.relative_to(resolved_root)
                except ValueError:
                    raise PathSecurityError(f"Path escapes workspace boundary: '{norm_target}'")

                # If file exists and is symlink, verify symlink target stays in workspace
                candidate_target = workspace_root / norm_target
                if candidate_target.is_symlink():
                    sym_target = candidate_target.resolve()
                    try:
                        sym_target.relative_to(resolved_root)
                    except ValueError:
                        raise PathSecurityError(f"Symlink points outside workspace root: '{norm_target}' -> '{sym_target}'")

        return changed_paths

    @classmethod
    def _validate_single_path(cls, path_str: str) -> None:
        """Validate an individual path string against traversal, absolute paths, and protected patterns."""
        if not path_str or not path_str.strip():
            raise PathSecurityError("Target path in diff cannot be empty.")

        clean = path_str.strip()

        # 1. Absolute path check (POSIX)
        if clean.startswith("/") or clean.startswith("\\"):
            raise PathSecurityError(f"Absolute path rejected in patch: '{clean}'")

        # 2. Windows drive check (e.g., C:\...)
        if cls.WINDOWS_DRIVE_REGEX.match(clean):
            raise PathSecurityError(f"Windows drive path rejected in patch: '{clean}'")

        # 3. Path traversal check (../ or ..\ or ..)
        parts = re.split(r"[/\\]", clean)
        if ".." in parts:
            raise PathSecurityError(f"Path traversal ('..') detected in patch target: '{clean}'")

        # 4. Protected path check: .git directory or files
        if parts[0].lower() == ".git":
            raise PathSecurityError(f"Modifying '.git' paths is strictly forbidden: '{clean}'")

        # 5. Protected file names and extensions (credentials, private keys, secrets)
        filename = parts[-1]
        if filename in cls.PROTECTED_EXACT_NAMES:
            raise PathSecurityError(f"Modifying protected security/credential file is forbidden: '{clean}'")

        suffix = Path(filename).suffix.lower()
        if suffix in cls.PROTECTED_EXTENSIONS:
            raise PathSecurityError(f"Modifying private key or certificate files is forbidden: '{clean}'")

        # 6. CI and sensitive configuration
        if parts[0].lower() == ".github":
            raise PathSecurityError(f"Modifying GitHub workflow or action paths requires human policy review: '{clean}'")
