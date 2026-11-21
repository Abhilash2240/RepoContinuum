"""Integration test for importing GitHub issues into task chains."""

from pathlib import Path
import pytest

from repocontinuum.domain.planning import ActorType, TaskStatus
from repocontinuum.github.client import FakeGitHubClient
from repocontinuum.github.sync import GitHubSyncService
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


def test_import_github_issue_into_task_chain(tmp_path: Path):
    """Verify issue is imported with untrusted boundary tags, status CREATED, and audit trail."""
    db_path = tmp_path / "sync_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)

    chain = service.create_chain(title="GitHub Sync Chain", repository_id="demo-repo")
    client = FakeGitHubClient()
    sync_service = GitHubSyncService(client, service)

    task = sync_service.import_issue_to_chain(
        chain_id=chain.id,
        owner="repocontinuum-org",
        repo="demo-repo",
        issue_number=42,
    )

    # 1. State must be CREATED (not automatically planned or patched)
    assert task.status in (TaskStatus.CREATED, TaskStatus.READY)
    assert task.status != TaskStatus.PLANNED
    assert "GitHub #42:" in task.title

    # 2. Issue body and comments must be wrapped in <UNTRUSTED_REPOSITORY_DATA>
    assert '<UNTRUSTED_REPOSITORY_DATA source="github_issue"' in task.description
    assert "</UNTRUSTED_REPOSITORY_DATA>" in task.description
    assert "Fix calculation precision" in task.description
    assert "charlie-qa" in task.description
    assert "reproduced this" in task.description

    # 3. Audit trail must record IMPORT_GITHUB_ISSUE
    events = repo.get_audit_events_for_chain(chain.id)
    import_events = [e for e in events if e.action == "IMPORT_GITHUB_ISSUE"]
    assert len(import_events) == 1
    assert import_events[0].metadata["issue_number"] == 42
    assert import_events[0].actor_type == ActorType.USER
