"""Integration tests for end-to-end repository indexing pipeline."""

import json
from pathlib import Path
import pytest
from repocontinuum.domain.models import ParseStatus, RepositorySnapshot
from repocontinuum.indexing.indexer import RepositoryIndexer


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a controlled multi-file fixture repository."""
    repo = tmp_path / "sample_repo"
    repo.mkdir()

    # Git metadata fixture
    git_dir = repo / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    heads = git_dir / "refs" / "heads"
    heads.mkdir(parents=True)
    fake_sha = "1234567890abcdef1234567890abcdef12345678"
    (heads / "main").write_text(f"{fake_sha}\n", encoding="utf-8")

    # Application package
    app = repo / "sample_app"
    app.mkdir()
    (app / "__init__.py").write_text('"""Sample App Package."""\n__version__ = "1.0.0"\n', encoding="utf-8")
    (app / "models.py").write_text(
        '''"""Data models."""
class User:
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
''',
        encoding="utf-8",
    )
    (app / "service.py").write_text(
        '''"""User service."""
from .models import User
import math

class UserService:
    def create_user(self, name: str) -> User:
        return User(username=name, email=f"{name}@example.com")
''',
        encoding="utf-8",
    )

    # Tests directory
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_user_service.py").write_text(
        '''"""Tests for user service."""
import pytest
from sample_app.service import UserService

def test_create_user():
    service = UserService()
    user = service.create_user("alice")
    assert user.username == "alice"
''',
        encoding="utf-8",
    )

    # A malformed file (syntax error) to verify scan does not abort
    (repo / "broken_module.py").write_text("def syntax_error(:\n    pass\n", encoding="utf-8")

    # Ignored folders
    (repo / ".venv").mkdir()
    (repo / ".venv" / "should_ignore.py").write_text("x = 1\n", encoding="utf-8")

    # Binary file
    (repo / "logo.bin").write_bytes(b"\x00\x01\x02\x03")

    return repo


def test_full_repository_indexing_pipeline(sample_repo: Path) -> None:
    """Verify that indexer processes valid files, discovers tests, isolates malformed files, and skips ignored files."""
    indexer = RepositoryIndexer()
    snapshot = indexer.index_repository(sample_repo)

    assert isinstance(snapshot, RepositorySnapshot)
    assert snapshot.repository_name == "sample_repo"
    assert snapshot.commit_sha == "1234567890abcdef1234567890abcdef12345678"
    assert snapshot.ref_name == "main"

    summary = snapshot.summary
    assert summary.indexed_python_files == 5  # __init__.py, models.py, service.py, test_user_service.py, broken_module.py
    assert summary.parse_failures == 1
    assert "broken_module.py" in snapshot.parse_failures
    assert snapshot.files["broken_module.py"].parse_status == ParseStatus.SYNTAX_ERROR

    # Check discovered classes and methods
    assert summary.total_classes >= 2  # User, UserService
    assert summary.total_test_cases >= 1  # test_create_user

    # Test file discovery & linkage
    test_file_meta = snapshot.files["tests/test_user_service.py"]
    assert len(test_file_meta.test_cases) == 1
    tc = test_file_meta.test_cases[0]
    assert tc.name == "test_create_user"
    assert "sample_app.service.UserService" in tc.linked_symbols or len(tc.linked_symbols) > 0


def test_deterministic_indexing(sample_repo: Path) -> None:
    """Verify that multiple indexing runs on unchanged repository produce deterministic results."""
    indexer = RepositoryIndexer()
    snapshot1 = indexer.index_repository(sample_repo)
    snapshot2 = indexer.index_repository(sample_repo)

    assert snapshot1.commit_sha == snapshot2.commit_sha
    assert snapshot1.config_hash == snapshot2.config_hash
    assert snapshot1.summary == snapshot2.summary

    for path, f1 in snapshot1.files.items():
        assert path in snapshot2.files
        f2 = snapshot2.files[path]
        assert f1.content_hash == f2.content_hash
        assert len(f1.symbols) == len(f2.symbols)
        assert len(f1.imports) == len(f2.imports)
        assert len(f1.test_cases) == len(f2.test_cases)


def test_json_export_and_load(sample_repo: Path, tmp_path: Path) -> None:
    """Verify serialization to JSON file and reload with schema validation."""
    indexer = RepositoryIndexer()
    snapshot = indexer.index_repository(sample_repo)

    json_file = tmp_path / "snapshot.json"
    RepositoryIndexer.export_json(snapshot, json_file)

    assert json_file.exists()
    reloaded = RepositoryIndexer.load_json(json_file)

    assert reloaded.repository_name == snapshot.repository_name
    assert reloaded.commit_sha == snapshot.commit_sha
    assert reloaded.summary.indexed_python_files == snapshot.summary.indexed_python_files
