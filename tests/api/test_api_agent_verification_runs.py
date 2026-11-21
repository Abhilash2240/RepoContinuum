"""API tests for agent runs and verification runs endpoints."""

import pytest
from fastapi.testclient import TestClient

from repocontinuum.api.app import create_app
from repocontinuum.api.dependencies import get_repository
from repocontinuum.domain.agent import AgentRun, AgentRunStatus
from repocontinuum.domain.verification import (
    CheckStatus,
    EvidenceReport,
    SandboxType,
    VerificationCheck,
    VerificationRun,
    VerificationRunStatus,
)
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


@pytest.fixture
def api_client_with_runs(tmp_path):
    db_path = tmp_path / "api_runs_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)

    chain = service.create_chain(title="Runs Chain", repository_id="runs-repo")
    task = service.add_task(chain_id=chain.id, title="Runs Task", acceptance_criteria=["Must run"])

    agent_run = AgentRun(
        id="arun-test-1234",
        chain_id=chain.id,
        task_id=task.id,
        provider="fake",
        model="fake-model",
        status=AgentRunStatus.VERIFICATION_PASSED,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=25,
        created_at="2026-11-21T18:00:00Z",
    )
    repo.save_agent_run(agent_run)

    vrun = VerificationRun(
        id="vrun-test-1234",
        patch_id="pat-test-1234",
        task_id=task.id,
        chain_id=chain.id,
        base_sha="a" * 40,
        workspace_id="ws-test",
        sandbox_type=SandboxType.FAKE,
        image_tag="python:3.13-slim",
        status=VerificationRunStatus.COMPLETED,
        has_regressions=False,
        started_at="2026-11-21T18:01:00Z",
        completed_at="2026-11-21T18:01:05Z",
        checks=[
            VerificationCheck(
                id="chk-1",
                name="python -m py_compile",
                command=["python", "-m", "py_compile"],
                status=CheckStatus.PASSED,
                exit_code=0,
                duration_ms=45,
            )
        ],
    )
    repo.save_verification_run(vrun)

    report = EvidenceReport(
        report_id="evrep-test-1234",
        repository_id="runs-repo",
        chain_id=chain.id,
        task_id=task.id,
        base_sha="a" * 40,
        patch_id="pat-test-1234",
        patch_hash="b" * 64,
        changed_files=["calc.py"],
        added_lines_count=3,
        removed_lines_count=0,
        workspace_id="ws-test",
        execution_image="python:3.13-slim",
        execution_image_digest=None,
        sandbox_type=SandboxType.FAKE,
        checks_executed=[
            VerificationCheck(
                id="chk-1",
                name="python -m py_compile",
                command=["python", "-m", "py_compile"],
                status=CheckStatus.PASSED,
                exit_code=0,
                duration_ms=45,
            )
        ],
        earlier_obligations_rechecked=[],
        regressions_detected=[],
        skipped_or_unsupported_checks=[],
        outstanding_risks=[],
        verification_conclusion=CheckStatus.PASSED,
        summary_markdown="# Verification Report\n\nAll checks passed cleanly.",
    )
    repo.save_evidence_report(report, run_id=vrun.id)

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    return TestClient(app), agent_run.id, vrun.id


def test_list_and_get_agent_runs(api_client_with_runs):
    client, run_id, _ = api_client_with_runs
    resp = client.get("/api/v1/agent-runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) >= 1
    assert runs[0]["id"] == run_id

    resp_single = client.get(f"/api/v1/agent-runs/{run_id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["provider"] == "fake"
    assert resp_single.json()["status"] == AgentRunStatus.VERIFICATION_PASSED.value


def test_list_and_get_verification_runs_and_evidence(api_client_with_runs):
    client, _, vrun_id = api_client_with_runs
    resp = client.get("/api/v1/verification-runs")
    assert resp.status_code == 200
    vruns = resp.json()
    assert len(vruns) >= 1
    assert vruns[0]["id"] == vrun_id

    resp_single = client.get(f"/api/v1/verification-runs/{vrun_id}")
    assert resp_single.status_code == 200
    assert resp_single.json()["sandbox_type"] == SandboxType.FAKE.value

    resp_ev = client.get(f"/api/v1/verification-runs/{vrun_id}/evidence")
    assert resp_ev.status_code == 200
    assert resp_ev.json()["verification_conclusion"] == CheckStatus.PASSED.value
    assert "Verification Report" in resp_ev.json()["summary_markdown"]
