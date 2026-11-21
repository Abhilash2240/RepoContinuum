"""End-to-end integration tests for Milestone 5 Dashboard and GitHub Read Integration."""

import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient

from repocontinuum.api.app import create_app
from repocontinuum.api.dependencies import get_repository
from repocontinuum.domain import (
    AgentRun,
    AgentRunStatus,
    CheckStatus,
    EvidenceReport,
    Obligation,
    ObligationStatus,
    SandboxType,
    TaskStatus,
    VerificationCheck,
    VerificationRun,
    VerificationRunStatus,
)
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


@pytest.fixture
def dashboard_e2e_setup(tmp_path, monkeypatch):
    """Set up a fully populated repository with tasks, runs, obligations, and mock GitHub."""
    db_path = tmp_path / "dashboard_e2e.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)

    # 1. Create a chain with tasks and dependency
    chain = service.create_chain(title="E2E Pipeline Maintenance", repository_id="repo-cont-e2e")
    t1 = service.add_task(
        chain_id=chain.id,
        title="Refactor Parser",
        description="Clean up AST walker",
        acceptance_criteria=["All AST tests pass"],
    )
    t2 = service.add_task(
        chain_id=chain.id,
        title="Update Symbol Indexer",
        description="Support type alias expressions",
        acceptance_criteria=["Aliases indexed correctly"],
    )
    service.add_dependency(chain_id=chain.id, predecessor_task_id=t1.id, successor_task_id=t2.id)

    # 2. Add an explicit obligation
    ob = Obligation(
        id="ob-e2e-001",
        chain_id=chain.id,
        source_task_id=t1.id,
        description="Preserve zero-regression AST parsing",
        verifier_ref="tests/unit/test_ast.py",
        status=ObligationStatus.ACTIVE,
    )
    repo.save_obligation(ob)

    # 3. Add an agent run
    agent_run = AgentRun(
        id="arun-e2e-001",
        chain_id=chain.id,
        task_id=t1.id,
        provider="fake",
        model="fake-model",
        status=AgentRunStatus.VERIFICATION_PASSED,
        prompt_tokens=420,
        completion_tokens=180,
        total_tokens=600,
        latency_ms=150,
        created_at="2026-11-21T18:00:00Z",
    )
    repo.save_agent_run(agent_run)

    # 4. Add a verification run with evidence report
    check = VerificationCheck(
        id="chk-e2e-1",
        name="pytest AST",
        command=["pytest", "tests/unit/test_ast.py"],
        status=CheckStatus.PASSED,
        exit_code=0,
        duration_ms=45,
    )
    v_run = VerificationRun(
        id="vrun-e2e-001",
        patch_id="pat-e2e-1234",
        task_id=t1.id,
        chain_id=chain.id,
        base_sha="a" * 40,
        workspace_id="ws-e2e",
        sandbox_type=SandboxType.FAKE,
        image_tag="python:3.13-slim",
        status=VerificationRunStatus.COMPLETED,
        has_regressions=False,
        started_at="2026-11-21T18:01:00Z",
        completed_at="2026-11-21T18:01:05Z",
        checks=[check],
    )
    repo.save_verification_run(v_run)

    report = EvidenceReport(
        report_id="evrep-e2e-001",
        repository_id="repo-cont-e2e",
        chain_id=chain.id,
        task_id=t1.id,
        base_sha="a" * 40,
        patch_id="pat-e2e-1234",
        patch_hash="b" * 64,
        changed_files=["ast_parser.py"],
        added_lines_count=12,
        removed_lines_count=2,
        workspace_id="ws-e2e",
        execution_image="python:3.13-slim",
        execution_image_digest=None,
        sandbox_type=SandboxType.FAKE,
        checks_executed=[check],
        earlier_obligations_rechecked=[],
        regressions_detected=[],
        skipped_or_unsupported_checks=[],
        outstanding_risks=[],
        verification_conclusion=CheckStatus.PASSED,
        summary_markdown="# Verification Report\n\nAll checks passed cleanly.",
    )
    repo.save_evidence_report(report, run_id=v_run.id)

    # 5. Environment configuration for mock GitHub App
    secret = "e2e_test_secret_98765"
    monkeypatch.setenv("REPOCONTINUUM_GITHUB_MOCK_MODE", "true")
    monkeypatch.setenv("REPOCONTINUUM_GITHUB_WEBHOOK_SECRET", secret)

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    client = TestClient(app)

    return {
        "client": client,
        "repo": repo,
        "chain_id": chain.id,
        "t1_id": t1.id,
        "t2_id": t2.id,
        "agent_run_id": agent_run.id,
        "verification_run_id": v_run.id,
        "webhook_secret": secret,
    }


def test_dashboard_static_frontend_served(dashboard_e2e_setup):
    """Test that the built React frontend is served at root."""
    client = dashboard_e2e_setup["client"]
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert '<div id="root">' in resp.text
    assert "RepoContinuum" in resp.text


def test_dashboard_summary_e2e(dashboard_e2e_setup):
    """Test dashboard summary endpoint aggregates chains, obligations, and runs."""
    client = dashboard_e2e_setup["client"]
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_chains"] == 1
    assert data["total_tasks"] == 2
    assert data["total_obligations"] == 3
    assert data["active_obligations"] == 3
    assert data["recent_agent_runs_count"] == 1
    assert data["recent_verification_runs_count"] == 1
    assert data["registered_repositories"] == ["repo-cont-e2e"]
    assert data["github"]["mode"] == "fake"


def test_task_chain_dag_visualizer_e2e(dashboard_e2e_setup):
    """Test chain inspection and DAG topological data structure."""
    client = dashboard_e2e_setup["client"]
    chain_id = dashboard_e2e_setup["chain_id"]
    t1_id = dashboard_e2e_setup["t1_id"]
    t2_id = dashboard_e2e_setup["t2_id"]

    # Chain detail
    resp = client.get(f"/api/v1/chains/{chain_id}")
    assert resp.status_code == 200
    chain_data = resp.json()
    assert chain_data["id"] == chain_id
    assert len(chain_data["tasks"]) == 2

    # Chain DAG
    resp_graph = client.get(f"/api/v1/chains/{chain_id}/graph")
    assert resp_graph.status_code == 200
    graph_data = resp_graph.json()
    assert graph_data["is_valid"] is True
    assert graph_data["topological_order"] == [t1_id, t2_id]
    assert len(graph_data["nodes"]) == 2
    assert len(graph_data["edges"]) == 1
    assert graph_data["edges"][0]["from"] == t1_id
    assert graph_data["edges"][0]["to"] == t2_id


def test_obligation_ledger_e2e(dashboard_e2e_setup):
    """Test retrieving obligations for a chain."""
    client = dashboard_e2e_setup["client"]
    chain_id = dashboard_e2e_setup["chain_id"]

    resp = client.get(f"/api/v1/chains/{chain_id}/obligations")
    assert resp.status_code == 200
    obligations = resp.json()
    assert len(obligations) == 3
    descriptions = [o["description"] for o in obligations]
    assert "Preserve zero-regression AST parsing" in descriptions
    assert "All AST tests pass" in descriptions


def test_agent_run_and_verification_telemetry_e2e(dashboard_e2e_setup):
    """Test telemetry inspection for agent runs and verification evidence."""
    client = dashboard_e2e_setup["client"]
    agent_run_id = dashboard_e2e_setup["agent_run_id"]
    v_run_id = dashboard_e2e_setup["verification_run_id"]

    # Agent runs
    resp_ar = client.get(f"/api/v1/agent-runs/{agent_run_id}")
    assert resp_ar.status_code == 200
    ar_data = resp_ar.json()
    assert ar_data["status"] == "VERIFICATION_PASSED"
    assert ar_data["prompt_tokens"] == 420
    assert ar_data["total_tokens"] == 600

    # Verification run
    resp_vr = client.get(f"/api/v1/verification-runs/{v_run_id}")
    assert resp_vr.status_code == 200
    vr_data = resp_vr.json()
    assert vr_data["status"] == "COMPLETED"
    assert vr_data["patch_id"] == "pat-e2e-1234"

    # Evidence report
    resp_ev = client.get(f"/api/v1/verification-runs/{v_run_id}/evidence")
    assert resp_ev.status_code == 200
    ev_data = resp_ev.json()
    assert ev_data["verification_conclusion"] == "PASSED"
    assert len(ev_data["checks_executed"]) == 1
    assert "Verification Report" in ev_data["summary_markdown"]


def test_github_issue_import_untrusted_e2e(dashboard_e2e_setup):
    """Test importing a GitHub issue wraps payload in untrusted repository data tags."""
    client = dashboard_e2e_setup["client"]
    chain_id = dashboard_e2e_setup["chain_id"]

    payload = {
        "owner": "repocontinuum-org",
        "repo": "demo-repo",
        "issue_number": 42,
    }
    resp = client.post(f"/api/v1/chains/{chain_id}/tasks/import-github-issue", json=payload)
    assert resp.status_code == 200
    resp_data = resp.json()
    assert resp_data["success"] is True
    task_data = resp_data["task"]
    assert task_data["status"] in ("CREATED", "READY")
    assert task_data["title"] == "GitHub #42: Fix calculation precision in math helper"
    assert '<UNTRUSTED_REPOSITORY_DATA source="github_issue"' in task_data["description"]
    assert "</UNTRUSTED_REPOSITORY_DATA>" in task_data["description"]
    assert "https://github.com/repocontinuum-org/demo-repo/issues/42" in task_data["description"]


def test_github_webhook_idempotency_e2e(dashboard_e2e_setup):
    """Test webhook verification and duplicate delivery ID idempotency."""
    client = dashboard_e2e_setup["client"]
    secret = dashboard_e2e_setup["webhook_secret"]

    body = json.dumps({"action": "opened", "issue": {"number": 101}}).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    delivery_id = "deliv-uuid-e2e-12345"

    headers = {
        "X-GitHub-Delivery": delivery_id,
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": sig,
        "Content-Type": "application/json",
    }

    # First delivery: processed/accepted
    resp1 = client.post("/api/v1/webhooks/github", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "accepted"
    assert resp1.json()["delivery_id"] == delivery_id

    # Second delivery with identical delivery ID: duplicate recognized idempotently
    resp2 = client.post("/api/v1/webhooks/github", content=body, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate"
    assert resp2.json()["delivery_id"] == delivery_id
