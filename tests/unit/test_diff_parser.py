"""Unit tests for unified diff parsing, validation, and content hashing."""

import pytest
from repocontinuum.domain.verification import FileDiff
from repocontinuum.patching.diff_parser import MalformedPatchError, UnifiedDiffParser


SAMPLE_VALID_DIFF = """--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,4 +1,5 @@
 def add(a: int, b: int) -> int:
-    return a - b
+    return a + b
+    # Fixed addition logic
"""

SAMPLE_MULTI_FILE_DIFF = """--- a/service.py
+++ b/service.py
@@ -1,3 +1,3 @@
-old_service = True
+new_service = True
--- a/config.py
+++ b/config.py
@@ -10,3 +10,4 @@
 timeout = 30
+retries = 3
"""

SAMPLE_CREATION_DIFF = """--- /dev/null
+++ b/new_module.py
@@ -0,0 +1,3 @@
+def helper():
+    return 100
"""

SAMPLE_DELETION_DIFF = """--- a/obsolete.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def dead_code():
-    pass
"""


def test_parse_valid_single_file_diff() -> None:
    """Verify parsing of standard unified diff for modified file."""
    diffs = UnifiedDiffParser.parse(SAMPLE_VALID_DIFF)
    assert len(diffs) == 1

    fd = diffs[0]
    assert isinstance(fd, FileDiff)
    assert fd.old_path == "src/calculator.py"
    assert fd.new_path == "src/calculator.py"
    assert fd.is_creation is False
    assert fd.is_deletion is False
    assert fd.added_lines == 2
    assert fd.removed_lines == 1
    assert len(fd.hunks) == 1

    hunk = fd.hunks[0]
    assert hunk.old_start == 1
    assert hunk.new_start == 1


def test_parse_multi_file_diff() -> None:
    """Verify parsing diff modifying multiple files."""
    diffs = UnifiedDiffParser.parse(SAMPLE_MULTI_FILE_DIFF)
    assert len(diffs) == 2
    paths = [d.new_path for d in diffs]
    assert paths == ["service.py", "config.py"]


def test_parse_file_creation_and_deletion() -> None:
    """Verify file creation and deletion diffs."""
    creation_diffs = UnifiedDiffParser.parse(SAMPLE_CREATION_DIFF)
    assert len(creation_diffs) == 1
    assert creation_diffs[0].is_creation is True
    assert creation_diffs[0].new_path == "new_module.py"

    deletion_diffs = UnifiedDiffParser.parse(SAMPLE_DELETION_DIFF)
    assert len(deletion_diffs) == 1
    assert deletion_diffs[0].is_deletion is True
    assert deletion_diffs[0].old_path == "obsolete.py"


def test_compute_patch_hash_deterministic() -> None:
    """Verify SHA-256 hash calculation is deterministic and normalizes newlines."""
    hash1 = UnifiedDiffParser.compute_patch_hash(SAMPLE_VALID_DIFF)
    hash2 = UnifiedDiffParser.compute_patch_hash(SAMPLE_VALID_DIFF.replace("\n", "\r\n"))
    assert hash1 == hash2
    assert len(hash1) == 64


def test_malformed_diff_rejected() -> None:
    """Verify malformed diffs raise MalformedPatchError."""
    # Empty diff
    with pytest.raises(MalformedPatchError, match="cannot be empty"):
        UnifiedDiffParser.parse("")

    # Garbage content without headers
    with pytest.raises(MalformedPatchError, match="No valid file diffs"):
        UnifiedDiffParser.parse("Just random prose text that is not a diff.")

    # Malformed hunk header syntax
    bad_hunk = """--- a/foo.py
+++ b/foo.py
@@ not_a_number @@
-a
+b
"""
    with pytest.raises(MalformedPatchError, match="Invalid hunk header"):
        UnifiedDiffParser.parse(bad_hunk)


def test_binary_patch_rejected() -> None:
    """Verify git binary patches are detected and rejected."""
    binary_diff = """diff --git a/logo.png b/logo.png
GIT binary patch
literal 50
zcmd^<f)8(G%h6;@o
"""
    with pytest.raises(MalformedPatchError, match="Binary diffs are not supported"):
        UnifiedDiffParser.parse(binary_diff)
