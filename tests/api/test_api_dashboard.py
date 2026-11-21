"""API integration tests for dashboard summary endpoints."""

import pytest
from fastapi.testclient import TestClient

from repocontinuum.api.app import create_app
from repocontinuum.api.dependencies import get_repository
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


@pytest.fixture
def client_with_data(tmp_path):
    db_path = tmp_path / "api_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)

    chain = service.create_chain(title="Test API Chain", repository_id="api-repo")
    t1 = service.add_task(chain_id=chain.id, title="Task 1", acceptance_criteria=["Criterion 1"])
    t2 = service.add_task(chain_id=chain.id, title="Task 2", acceptance_criteria=["Criterion 2"])
    service.add_dependency(chain_id=chain.id, predecessor_task_id=t1.id, successor_task_id=t2.id)

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


def test_get_dashboard_summary(client_with_data):
    """Verify /api/v1/dashboard/summary returns real persisted metrics."""
    resp = client_with_data.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_chains"] == 1
    assert data["total_tasks"] == 2
    assert data["active_obligations"] == 2
    assert "api-repo" in data["registered_repositories"]
    assert "github" in data
    assert data["github"]["mode"] == "fake"
