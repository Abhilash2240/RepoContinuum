"""API tests for benchmark metrics and report endpoints."""

import pytest
from fastapi.testclient import TestClient
from repocontinuum.api.app import create_app
from repocontinuum.api.dependencies import get_repository
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository


@pytest.fixture
def bmk_client(tmp_path):
    db_path = tmp_path / "bmk_api_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app)


def test_get_benchmark_summary_and_report_api(bmk_client):
    """Test retrieving benchmark summary and report markdown."""
    # Summary
    resp_sum = bmk_client.get("/api/v1/benchmarks/summary")
    assert resp_sum.status_code == 200
    data = resp_sum.json()
    assert "baselines" in data
    assert "baseline_a_isolated_issue" in data["baselines"]
    assert "baseline_c_full_repocontinuum" in data["baselines"]

    # Report
    resp_rep = bmk_client.get("/api/v1/benchmarks/report")
    assert resp_rep.status_code == 200
    assert "markdown" in resp_rep.json()
    assert "# RepoContinuum — Milestone 6 Benchmark Evaluation Report" in resp_rep.json()["markdown"]


def test_run_benchmark_endpoint_persists_to_db(bmk_client):
    """Test triggering a benchmark execution endpoint stores runs in database."""
    resp = bmk_client.post("/api/v1/benchmarks/run", json={"baseline": "all", "seed": 99})
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed"] == 99

    # Verify runs were saved in DB
    resp_runs = bmk_client.get("/api/v1/benchmarks/runs")
    assert resp_runs.status_code == 200
    runs = resp_runs.json()
    assert len(runs) >= 3
