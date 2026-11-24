"""Security boundary and trust isolation tests."""

import os
from pathlib import Path
import pytest
from repocontinuum.domain.models import SkipReason
from repocontinuum.indexing.file_walker import FileWalker
from repocontinuum.indexing.indexer import RepositoryIndexer


def test_zero_code_execution_guarantee(tmp_path: Path) -> None:
    """CRITICAL SECURITY TEST: Ensure scanned repository code is NEVER executed or imported."""
    canary_file = tmp_path / "CANARY_PWNED.txt"
    if canary_file.exists():
        canary_file.unlink()

    repo = tmp_path / "hostile_repo"
    repo.mkdir()

    # Create hostile Python module that would write a canary or mutate env if executed
    payload_content = f'''
import os
from pathlib import Path

# Malicious payload that would trigger on import/execution
Path(r"{canary_file}").write_text("PWNED")
os.environ["REPO_CODE_EXECUTED"] = "TRUE"

def normal_looking_function():
    return 42
'''
    (repo / "malicious.py").write_text(payload_content, encoding="utf-8")

    # Run the indexer
    indexer = RepositoryIndexer()
    snapshot = indexer.index_repository(repo)

    # 1. Assert canary was NOT written
    assert not canary_file.exists(), "SECURITY VIOLATION: Target repository code was executed on the host!"

    # 2. Assert environment was NOT mutated
    assert "REPO_CODE_EXECUTED" not in os.environ, "SECURITY VIOLATION: Host environment was mutated by scanned code!"

    # 3. Assert symbols were still accurately extracted via static AST
    assert "malicious.py" in snapshot.files
    sym_names = [s.name for s in snapshot.files["malicious.py"].symbols]
    assert "normal_looking_function" in sym_names


def test_path_traversal_and_invalid_root_rejection(tmp_path: Path) -> None:
    """Verify that invalid repository paths or traversal attempts are strictly rejected."""
    indexer = RepositoryIndexer()
    non_existent = tmp_path / "does_not_exist"

    with pytest.raises(ValueError, match="not a valid directory"):
        indexer.index_repository(non_existent)


def test_symlink_escape_rejection(tmp_path: Path) -> None:
    """Verify that symlinks resolving outside the repository root are skipped."""
    outside_dir = (tmp_path / "outside_secret").resolve()
    outside_dir.mkdir(parents=True, exist_ok=True)
    secret_file = outside_dir / "secret.py"
    secret_file.write_text("SECRET_KEY = 'super_secret'\n", encoding="utf-8")

    repo_dir = (tmp_path / "repo").resolve()
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "normal.py").write_text("x = 1\n", encoding="utf-8")

    symlink_file = repo_dir / "escaped_link.py"
    try:
        symlink_file.symlink_to(secret_file)
    except (OSError, NotImplementedError):
        # On Windows, symlink creation may require Developer Mode / admin privilege
        pytest.skip("Symlink creation requires elevated privilege on this Windows host")

    walker = FileWalker(repo_root=repo_dir, ignored_directories=set())
    result = walker.walk()

    rel_python = [p.resolve().relative_to(repo_dir).as_posix() for p in result.python_files]
    assert "escaped_link.py" not in rel_python

    skipped_reasons = {sf.path: sf.reason for sf in result.skipped_files}
    assert "escaped_link.py" in skipped_reasons
    assert skipped_reasons["escaped_link.py"] == SkipReason.SYMLINK_ESCAPE
