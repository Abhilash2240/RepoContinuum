"""Integration tests for applying unified diffs to files in a workspace."""

from pathlib import Path
import pytest
from repocontinuum.patching.applier import PatchApplicationError, UnifiedDiffApplier
from repocontinuum.patching.diff_parser import UnifiedDiffParser


def test_apply_modification_diff(tmp_path: Path) -> None:
    """Verify applying a unified diff to modify existing source file."""
    f = tmp_path / "math_lib.py"
    f.write_text("def calculate(x):\n    return x * 1\n", encoding="utf-8")

    diff_text = """--- a/math_lib.py
+++ b/math_lib.py
@@ -1,2 +1,2 @@
 def calculate(x):
-    return x * 1
+    return x * 2
"""
    diffs = UnifiedDiffParser.parse(diff_text)
    UnifiedDiffApplier.apply_diffs(diffs, tmp_path)

    updated_content = f.read_text(encoding="utf-8")
    assert "return x * 2" in updated_content
    assert "return x * 1" not in updated_content


def test_apply_file_creation_diff(tmp_path: Path) -> None:
    """Verify creating a new file in nested subdirectory via diff."""
    diff_text = """--- /dev/null
+++ b/pkg/new_file.py
@@ -0,0 +1,2 @@
+def brand_new():
+    return 42
"""
    diffs = UnifiedDiffParser.parse(diff_text)
    UnifiedDiffApplier.apply_diffs(diffs, tmp_path)

    new_file = tmp_path / "pkg" / "new_file.py"
    assert new_file.exists()
    assert "def brand_new():" in new_file.read_text(encoding="utf-8")


def test_apply_file_deletion_diff(tmp_path: Path) -> None:
    """Verify deleting a file via diff."""
    f = tmp_path / "obsolete.py"
    f.write_text("pass\n", encoding="utf-8")
    assert f.exists()

    diff_text = """--- a/obsolete.py
+++ /dev/null
@@ -1,1 +0,0 @@
-pass
"""
    diffs = UnifiedDiffParser.parse(diff_text)
    UnifiedDiffApplier.apply_diffs(diffs, tmp_path)

    assert not f.exists()


def test_apply_context_mismatch_raises_error(tmp_path: Path) -> None:
    """Verify that applying a patch with mismatched context raises PatchApplicationError."""
    f = tmp_path / "file.py"
    f.write_text("completely different content\n", encoding="utf-8")

    diff_text = """--- a/file.py
+++ b/file.py
@@ -1,2 +1,2 @@
 expected content line
-old line
+new line
"""
    diffs = UnifiedDiffParser.parse(diff_text)
    with pytest.raises(PatchApplicationError, match="context mismatch"):
        UnifiedDiffApplier.apply_diffs(diffs, tmp_path)
