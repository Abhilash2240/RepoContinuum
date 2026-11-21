"""Unified diff application engine applying validated patches to target files."""

from __future__ import annotations

from pathlib import Path
from typing import List
from repocontinuum.domain.verification import DiffHunk, FileDiff


class PatchApplicationError(Exception):
    """Raised when a patch cannot be cleanly applied to target files."""


class UnifiedDiffApplier:
    """Applies parsed unified diffs to files within an isolated directory."""

    @classmethod
    def apply_diffs(cls, file_diffs: List[FileDiff], target_root: Path) -> None:
        """Apply a collection of file diffs to target_root directory."""
        resolved_root = target_root.resolve()

        for fdiff in file_diffs:
            if fdiff.is_deletion:
                target_file = (resolved_root / fdiff.old_path).resolve()
                if target_file.exists():
                    target_file.unlink()
                continue

            target_file = (resolved_root / fdiff.new_path).resolve()

            if fdiff.is_creation:
                # Create brand new file from additions
                new_content_lines: List[str] = []
                for hunk in fdiff.hunks:
                    for line in hunk.lines:
                        if line.startswith("+"):
                            new_content_lines.append(line[1:])
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text("\n".join(new_content_lines) + ("\n" if new_content_lines else ""), encoding="utf-8")
                continue

            # File modification
            if not target_file.exists():
                raise PatchApplicationError(
                    f"Target file to modify does not exist: '{fdiff.new_path}'"
                )

            try:
                original_text = target_file.read_text(encoding="utf-8")
            except OSError as e:
                raise PatchApplicationError(f"Could not read target file '{fdiff.new_path}': {e}")

            original_lines = original_text.splitlines()
            modified_lines = cls._apply_hunks_to_lines(original_lines, fdiff.hunks, fdiff.new_path)

            target_file.write_text(
                "\n".join(modified_lines) + ("\n" if modified_lines else ""),
                encoding="utf-8",
            )

    @classmethod
    def _apply_hunks_to_lines(
        cls,
        lines: List[str],
        hunks: List[DiffHunk],
        file_path: str,
    ) -> List[str]:
        """Apply hunks sequentially to an array of lines."""
        current_lines = list(lines)
        offset = 0

        for hunk in hunks:
            # 1-based old_start converted to 0-based index adjusted by prior hunk offset
            expected_start = (hunk.old_start - 1) + offset

            # Check if context matches at expected_start
            match_index = cls._find_matching_index(current_lines, hunk, expected_start)
            if match_index is None:
                raise PatchApplicationError(
                    f"Hunk application failed for '{file_path}' at line {hunk.old_start}: context mismatch"
                )

            # Build replacement slice
            new_slice: List[str] = []
            old_slice_len = 0

            for line in hunk.lines:
                if line.startswith(" "):
                    new_slice.append(line[1:])
                    old_slice_len += 1
                elif line.startswith("-"):
                    old_slice_len += 1
                elif line.startswith("+"):
                    new_slice.append(line[1:])

            # Verify old slice matches
            for idx in range(old_slice_len):
                if match_index + idx >= len(current_lines):
                    break

            # Replace lines
            current_lines[match_index : match_index + old_slice_len] = new_slice
            offset += (len(new_slice) - old_slice_len)

        return current_lines

    @classmethod
    def _find_matching_index(
        cls,
        lines: List[str],
        hunk: DiffHunk,
        expected_index: int,
    ) -> int | None:
        """Find the index where hunk context lines match the target lines."""
        # Expected context to match (space and minus lines)
        context_pattern: List[str] = []
        for line in hunk.lines:
            if line.startswith(" ") or line.startswith("-"):
                context_pattern.append(line[1:])

        if not context_pattern:
            return max(0, min(expected_index, len(lines)))

        pattern_len = len(context_pattern)

        # 1. Try exact expected index first
        if 0 <= expected_index <= len(lines) - pattern_len:
            if lines[expected_index : expected_index + pattern_len] == context_pattern:
                return expected_index

        # 2. Search small delta neighborhood (-5 to +5)
        for delta in range(1, 10):
            # Check earlier
            idx = expected_index - delta
            if 0 <= idx <= len(lines) - pattern_len:
                if lines[idx : idx + pattern_len] == context_pattern:
                    return idx
            # Check later
            idx = expected_index + delta
            if 0 <= idx <= len(lines) - pattern_len:
                if lines[idx : idx + pattern_len] == context_pattern:
                    return idx

        # 3. Exhaustive search if small neighborhood missed
        for idx in range(len(lines) - pattern_len + 1):
            if lines[idx : idx + pattern_len] == context_pattern:
                return idx

        return None
