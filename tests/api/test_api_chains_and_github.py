"""API integration tests for task chains, DAG visualizer, and GitHub endpoints."""

import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient

from repocontinuum.api.app import create_app
from repocontinuum.api.dependencies import get_repository
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_chains_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)

    chain = service.create_chain(title="DAG Chain", repository_id="api-repo")
    t1 = service.add_task(chain_id=chain.id, title="Task 1", acceptance_criteria=["Criterion 1"])
    t2 = service.add_task(chain_id=chain.id, title="Task 2", acceptance_criteria=["Criterion 2"])
    service.add_dependency(chain_id=chain.id, predecessor_task_id=t1.id, successor_task_id=t2.id)

    monkeypatch.setenv("REPOCONTINUUM_GITHUB_MOCK_MODE", "true")
    monkeypatch.setenv("REPOCONTINUUM_GITHUB_WEBHOOK_SECRET", "test_webhook_secret")

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app), chain.id


def test_list_and_get_chains(api_client):
    client, chain_id = api_client
    resp = client.get("/api/v1/chains")
    assert resp.status_code == 200
    chains = resp.json()
    assert len(chains) == 1
    assert chains[0]["id"] == chain_id

    resp_single = client.get(f"/api/v1/chains/{chain_id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["title"] == "DAG Chain"


def test_get_chain_graph(api_client):
    client, chain_id = api_client
    resp = client.get(f"/api/v1/chains/{chain_id}/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert len(data["topological_order"]) == 2


def test_github_read_endpoints(api_client):
    client, _ = api_client
    # Status
    res_status = client.get("/api/v1/github/status")
    assert res_status.status_code == 200
    assert res_status.json()["mode"] == "fake"

    # Repos
    res_repos = client.get("/api/v1/github/repositories")
    assert res_repos.status_code == 200
    assert len(res_repos.json()) >= 1

    # Issues
    res_issues = client.get("/api/v1/github/repositories/repocontinuum-org/demo-repo/issues")
    assert res_issues.status_code == 200
    assert len(res_issues.json()) == 2

    # Single Issue with comments
    res_issue = client.get("/api/v1/github/repositories/repocontinuum-org/demo-repo/issues/42")
    assert res_issue.status_code == 200
    assert len(res_issue.json()["comments"]) == 1

    # Pulls
    res_pulls = client.get("/api/v1/github/repositories/repocontinuum-org/demo-repo/pulls")
    assert res_pulls.status_code == 200
    assert len(res_pulls.json()) == 1


def test_import_github_issue_api(api_client):
    client, chain_id = api_client
    payload = {
        "owner": "repocontinuum-org",
        "repo": "demo-repo",
        "issue_number": 42,
    }
    resp = client.post(f"/api/v1/chains/{chain_id}/tasks/import-github-issue", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "GitHub #42:" in data["task"]["title"]


def test_github_webhook_hmac_and_idempotency(api_client):
    client, _ = api_client
    payload = json.dumps({"action": "opened", "issue": {"number": 99}}).encode("utf-8")
    secret = "test_webhook_secret"

    signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    headers = {
        "X-GitHub-Delivery": "delivery-unique-12345",
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": signature,
        "Content-Type": "application/json",
    }

    # 1. First delivery -> accepted
    resp1 = client.post("/api/v1/webhooks/github", data=payload, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "accepted"

    # 2. Duplicate delivery -> duplicate
    resp2 = client.post("/api/v1/webhooks/github", data=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"

    # 3. Tampered payload -> rejected (401)
    tampered_payload = json.dumps({"action": "tampered"}).encode("utf-8")
    resp_tampered = client.post("/api/v1/webhooks/github", data=tampered_payload, headers=headers)
    assert resp_tampered.status_code == 401
