"""Strict unified diff parser, syntax validator, and hash calculator."""

from __future__ import annotations

import hashlib
import re
from typing import List, Tuple
from repocontinuum.domain.verification import DiffHunk, FileDiff


class PatchError(Exception):
    """Base exception for patch parsing and validation failures."""


class MalformedPatchError(PatchError):
    """Raised when unified diff syntax is malformed or invalid."""


class UnifiedDiffParser:
    """Strict parser for unified diff format without external dependencies."""

    # Matches @@ -1,5 +1,6 @@ optional function name
    HUNK_HEADER_REGEX = re.compile(
        r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(?: (.*))?$"
    )

    @classmethod
    def compute_patch_hash(cls, diff_content: str) -> str:
        """Compute deterministic SHA-256 hash of normalized patch content."""
        # Normalize newlines
        normalized = diff_content.replace("\r\n", "\n").strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @classmethod
    def parse(cls, diff_content: str) -> List[FileDiff]:
        """Parse unified diff text into structured FileDiff models."""
        if not diff_content or not diff_content.strip():
            raise MalformedPatchError("Patch content cannot be empty.")

        # Check for binary diff indicators
        if "GIT binary patch" in diff_content or "Binary files " in diff_content:
            raise MalformedPatchError("Binary diffs are not supported; patch must be text only.")

        lines = diff_content.replace("\r\n", "\n").split("\n")
        file_diffs: List[FileDiff] = []

        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # Look for diff file header
            if line.startswith("diff --git ") or line.startswith("--- "):
                old_path = None
                new_path = None

                # If diff --git line
                if line.startswith("diff --git "):
                    parts = line.split()
                    if len(parts) >= 4:
                        old_path = cls._clean_git_prefix(parts[2])
                        new_path = cls._clean_git_prefix(parts[3])
                    i += 1

                # Advance until --- and +++
                while i < n and not lines[i].startswith("--- "):
                    # Check for file mode or binary markers
                    if lines[i].startswith("Binary files "):
                        raise MalformedPatchError("Binary diffs are not supported.")
                    i += 1

                if i >= n:
                    break

                # Parse --- line
                dash_line = lines[i]
                old_raw = dash_line[4:].split("\t")[0].strip()
                old_path = old_path or cls._clean_git_prefix(old_raw)
                i += 1

                if i >= n or not lines[i].startswith("+++ "):
                    raise MalformedPatchError(f"Malformed diff: missing '+++ ' line after '{dash_line}'")

                # Parse +++ line
                plus_line = lines[i]
                new_raw = plus_line[4:].split("\t")[0].strip()
                new_path = new_path or cls._clean_git_prefix(new_raw)
                i += 1

                is_creation = (old_raw == "/dev/null")
                is_deletion = (new_raw == "/dev/null")
                is_rename = (old_path != new_path and not is_creation and not is_deletion)

                target_path = new_path if not is_deletion else old_path

                # Parse hunks for this file
                hunks: List[DiffHunk] = []
                total_added = 0
                total_removed = 0

                while i < n and lines[i].startswith("@@"):
                    hunk, added, removed, next_idx = cls._parse_hunk(lines, i)
                    hunks.append(hunk)
                    total_added += added
                    total_removed += removed
                    i = next_idx

                if not hunks and not is_creation and not is_deletion:
                    raise MalformedPatchError(f"File diff for '{target_path}' contains no valid hunks.")

                file_diffs.append(
                    FileDiff(
                        old_path=old_path or target_path,
                        new_path=new_path or target_path,
                        is_creation=is_creation,
                        is_deletion=is_deletion,
                        is_rename=is_rename,
                        hunks=hunks,
                        added_lines=total_added,
                        removed_lines=total_removed,
                    )
                )
            else:
                i += 1

        if not file_diffs:
            raise MalformedPatchError("No valid file diffs found in patch content.")

        return file_diffs

    @classmethod
    def _parse_hunk(cls, lines: List[str], start_idx: int) -> Tuple[DiffHunk, int, int, int]:
        """Parse an individual hunk starting at @@ line."""
        header_line = lines[start_idx]
        match = cls.HUNK_HEADER_REGEX.match(header_line)
        if not match:
            raise MalformedPatchError(f"Invalid hunk header syntax: '{header_line}'")

        old_start = int(match.group(1))
        old_lines = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_lines = int(match.group(4)) if match.group(4) else 1

        hunk_lines: List[str] = []
        added_count = 0
        removed_count = 0

        i = start_idx + 1
        n = len(lines)

        while i < n:
            line = lines[i]
            # End of hunk if another hunk begins or another diff begins
            if line.startswith("@@") or line.startswith("diff --git ") or line.startswith("--- "):
                break

            if not line:
                # Trailing empty line or empty context line
                if i == n - 1:
                    i += 1
                    break
                # Could be an empty context line
                hunk_lines.append(" ")
                i += 1
                continue

            first_char = line[0]
            if first_char in ("+", "-", " "):
                hunk_lines.append(line)
                if first_char == "+":
                    added_count += 1
                elif first_char == "-":
                    removed_count += 1
                i += 1
            elif line.startswith("\\ No newline at end of file"):
                # Standard unified diff note
                i += 1
            else:
                # Unexpected character outside standard hunk
                break

        hunk = DiffHunk(
            old_start=old_start,
            old_lines=old_lines,
            new_start=new_start,
            new_lines=new_lines,
            header=header_line,
            lines=hunk_lines,
        )

        return hunk, added_count, removed_count, i

    @staticmethod
    def _clean_git_prefix(path_str: str) -> str:
        """Strip Git standard a/ or b/ prefixes."""
        if path_str == "/dev/null":
            return "/dev/null"
        if path_str.startswith("a/") or path_str.startswith("b/"):
            return path_str[2:]
        return path_str
