"""Unit tests for patch security boundaries, path traversal guards, and protected paths."""

import pytest
from repocontinuum.domain.verification import DiffHunk, FileDiff
from repocontinuum.patching.security import PatchSecurityValidator, PathSecurityError


def _make_file_diff(path: str) -> FileDiff:
    return FileDiff(
        old_path=path,
        new_path=path,
        hunks=[DiffHunk(old_start=1, old_lines=1, new_start=1, new_lines=1, header="@@ -1,1 +1,1 @@", lines=["-a", "+b"])],
    )


def test_safe_paths_accepted() -> None:
    """Verify normal project relative paths pass validation."""
    diffs = [
        _make_file_diff("src/app/main.py"),
        _make_file_diff("tests/test_main.py"),
    ]
    paths = PatchSecurityValidator.validate_patch_security(diffs)
    assert paths == ["src/app/main.py", "tests/test_main.py"]


def test_path_traversal_rejected() -> None:
    """Verify ../ and ..\\ path traversal attempts are rejected."""
    with pytest.raises(PathSecurityError, match="Path traversal"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("../outside.py")])

    with pytest.raises(PathSecurityError, match="Path traversal"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("foo/../../escape.py")])

    with pytest.raises(PathSecurityError, match="Path traversal"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff(r"foo\..\escape.py")])


def test_absolute_paths_rejected() -> None:
    """Verify POSIX absolute paths are rejected."""
    with pytest.raises(PathSecurityError, match="Absolute path"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("/etc/passwd")])

    with pytest.raises(PathSecurityError, match="Absolute path"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("\\Windows\\System32\\cmd.exe")])


def test_windows_drive_paths_rejected() -> None:
    """Verify Windows drive letters (C:, D:) are rejected."""
    with pytest.raises(PathSecurityError, match="Windows drive path"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("C:\\Users\\admin\\secret.py")])

    with pytest.raises(PathSecurityError, match="Windows drive path"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("D:payload.py")])


def test_git_path_protection() -> None:
    """Verify modifying .git directory or files is forbidden."""
    with pytest.raises(PathSecurityError, match="'.git' paths is strictly forbidden"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff(".git/config")])

    with pytest.raises(PathSecurityError, match="'.git' paths is strictly forbidden"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff(".git/hooks/pre-commit")])


def test_credential_and_secret_files_protected() -> None:
    """Verify modifying .env, private keys, and credential stores is forbidden."""
    with pytest.raises(PathSecurityError, match="protected security/credential file"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff(".env")])

    with pytest.raises(PathSecurityError, match="protected security/credential file"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff(".env.production")])

    with pytest.raises(PathSecurityError, match="protected security/credential file"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("id_rsa")])

    with pytest.raises(PathSecurityError, match="private key or certificate"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("certs/server.pem")])

    with pytest.raises(PathSecurityError, match="private key or certificate"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff("secrets/private.key")])


def test_github_ci_policy_protection() -> None:
    """Verify modifying .github workflows is rejected for human review."""
    with pytest.raises(PathSecurityError, match="GitHub workflow"):
        PatchSecurityValidator.validate_patch_security([_make_file_diff(".github/workflows/ci.yml")])


def test_duplicate_target_paths_rejected() -> None:
    """Verify a patch cannot modify the same target path twice."""
    diffs = [
        _make_file_diff("src/service.py"),
        _make_file_diff("src/service.py"),
    ]
    with pytest.raises(PathSecurityError, match="Duplicate target path"):
        PatchSecurityValidator.validate_patch_security(diffs)
