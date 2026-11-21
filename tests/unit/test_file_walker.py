"""Unit tests for safe repository file traversal."""

from pathlib import Path
import pytest
from repocontinuum.domain.models import SkipReason
from repocontinuum.indexing.file_walker import FileWalker


def test_ignore_rules_and_directories(tmp_path: Path) -> None:
    """Verify that default ignored directories (.git, .venv, etc.) are skipped."""
    (tmp_path / "valid.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.py").write_text("secret = True\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "env_lib.py").write_text("lib = True\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cache.pyc").write_bytes(b"\x00\x01\x02")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "script.py").write_text("console.log()\n", encoding="utf-8")

    walker = FileWalker(
        repo_root=tmp_path,
        ignored_directories={".git", ".venv", "__pycache__", "node_modules"},
    )
    result = walker.walk()

    # Only valid.py should be collected as a Python file
    rel_python = [p.relative_to(tmp_path).as_posix() for p in result.python_files]
    assert rel_python == ["valid.py"]


def test_binary_file_detection(tmp_path: Path) -> None:
    """Verify that files with null bytes are skipped as binary."""
    (tmp_path / "text.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00")
    (tmp_path / "fake_py.py").write_bytes(b"# Python comment\x00with null byte")

    walker = FileWalker(
        repo_root=tmp_path,
        ignored_directories=set(),
    )
    result = walker.walk()

    rel_python = [p.relative_to(tmp_path).as_posix() for p in result.python_files]
    assert rel_python == ["text.py"]

    skipped_reasons = {sf.path: sf.reason for sf in result.skipped_files}
    assert skipped_reasons["fake_py.py"] == SkipReason.BINARY


def test_oversized_file_skipping(tmp_path: Path) -> None:
    """Verify that files exceeding the byte limit are marked oversized and skipped."""
    small = tmp_path / "small.py"
    small.write_text("x = 1\n", encoding="utf-8")

    big = tmp_path / "big.py"
    big.write_bytes(b"a" * 2000)

    walker = FileWalker(
        repo_root=tmp_path,
        ignored_directories=set(),
        max_file_size_bytes=1000,
    )
    result = walker.walk()

    rel_python = [p.relative_to(tmp_path).as_posix() for p in result.python_files]
    assert rel_python == ["small.py"]

    skipped = {sf.path: sf.reason for sf in result.skipped_files}
    assert skipped["big.py"] == SkipReason.OVERSIZED


def test_posix_path_preservation(tmp_path: Path) -> None:
    """Verify that walked paths preserve POSIX slashes across subdirectories."""
    nested = tmp_path / "pkg" / "subpkg"
    nested.mkdir(parents=True)
    (nested / "mod.py").write_text("val = 10\n", encoding="utf-8")

    walker = FileWalker(repo_root=tmp_path, ignored_directories=set())
    result = walker.walk()

    posix_path = result.python_files[0].relative_to(tmp_path).as_posix()
    assert "\\" not in posix_path
    assert posix_path == "pkg/subpkg/mod.py"
