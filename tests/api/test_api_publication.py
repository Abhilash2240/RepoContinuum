"""API integration tests for publication approval and pull-request endpoints."""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from repocontinuum.api.app import create_app
from repocontinuum.api.dependencies import get_publisher, get_repository
from repocontinuum.domain.planning import MaintenanceTask, TaskChain
from repocontinuum.domain.verification import (
    CheckStatus,
    EvidenceReport,
    Patch,
    SandboxType,
    VerificationCheck,
    VerificationRun,
    VerificationRunStatus,
)
from repocontinuum.github.publisher import FakeGitHubPublisher
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository


@pytest.fixture
def pub_api_client(tmp_path):
    db_path = tmp_path / "pub_api_test.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)

    # 1. Setup chain & task
    chain = TaskChain(id="chn-pub-1", repository_id="owner/repo", title="Pub Chain")
    repo.save_chain(chain)

    task = MaintenanceTask(
        id="tsk-pub-1",
        chain_id=chain.id,
        title="Fix precision",
        description="Replace float with Decimal",
    )
    repo.save_task(task)

    # 2. Setup patch
    patch = Patch(
        id="pat-pub-1",
        task_id=task.id,
        repository_id="owner/repo",
        base_sha="a" * 40,
        patch_hash="c" * 64,
        changed_paths=["calc.py"],
        total_added_lines=2,
        total_removed_lines=1,
        diff_content="--- a/calc.py\n+++ b/calc.py\n@@ -1 +1 @@\n-float\n+Decimal\n",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_patch(patch)

    # 3. Setup verification run & evidence report
    vrun = VerificationRun(
        id="vrun-pub-1",
        patch_id=patch.id,
        task_id=task.id,
        chain_id=chain.id,
        base_sha=patch.base_sha,
        workspace_id="ws-pub",
        sandbox_type=SandboxType.FAKE,
        image_tag="python:3.13-slim",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        status=VerificationRunStatus.COMPLETED,
    )
    repo.save_verification_run(vrun)

    report = EvidenceReport(
        report_id="evrep-pub-1",
        repository_id="owner/repo",
        chain_id=chain.id,
        task_id=task.id,
        base_sha=patch.base_sha,
        patch_id=patch.id,
        patch_hash=patch.patch_hash,
        changed_files=patch.changed_paths,
        added_lines_count=patch.total_added_lines,
        removed_lines_count=patch.total_removed_lines,
        workspace_id="ws-pub",
        sandbox_type=SandboxType.FAKE,
        execution_image="python:3.13-slim",
        execution_image_digest=None,
        checks_executed=[
            VerificationCheck(
                id="chk-1",
                name="test",
                command=["pytest"],
                status=CheckStatus.PASSED,
                exit_code=0,
                duration_ms=10,
            )
        ],
        earlier_obligations_rechecked=[],
        regressions_detected=[],
        skipped_or_unsupported_checks=[],
        outstanding_risks=[],
        verification_conclusion=CheckStatus.PASSED,
        summary_markdown="# Report\nPassed.",
    )
    repo.save_evidence_report(report, run_id=vrun.id)

    fake_publisher = FakeGitHubPublisher()

    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_publisher] = lambda: fake_publisher

    return TestClient(app), task.id, chain.id, patch.id, vrun.id


def test_publication_lifecycle_api(pub_api_client):
    """Test requesting approval, granting approval, and publishing PR via REST API."""
    client, task_id, chain_id, patch_id, vrun_id = pub_api_client

    # 1. Request approval
    req_payload = {
        "task_id": task_id,
        "chain_id": chain_id,
        "patch_id": patch_id,
        "verification_run_id": vrun_id,
        "repo_owner": "owner",
        "repo_name": "repo",
        "target_base_branch": "main",
    }
    resp_req = client.post("/api/v1/publications/approvals/request", json=req_payload)
    assert resp_req.status_code == 200
    approval_data = resp_req.json()
    approval_id = approval_data["id"]
    assert approval_data["status"] == "AWAITING_APPROVAL"
    assert approval_data["patch_hash"] == "c" * 64

    # 2. List approvals
    resp_list = client.get("/api/v1/publications/approvals")
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 1

    # 3. Grant approval
    appr_payload = {"approver_identity": "senior-eng@company.com", "validity_hours": 24}
    resp_appr = client.post(f"/api/v1/publications/approvals/{approval_id}/approve", json=appr_payload)
    assert resp_appr.status_code == 200
    assert resp_appr.json()["status"] == "APPROVED"
    assert resp_appr.json()["approver_identity"] == "senior-eng@company.com"

    # 4. Publish approved patch
    resp_pub = client.post(f"/api/v1/publications/approvals/{approval_id}/publish", json={"require_real_sandbox": False})
    assert resp_pub.status_code == 200
    pr_data = resp_pub.json()
    assert pr_data["pr_number"] == 101
    assert "https://github.com/owner/repo/pull/101" in pr_data["html_url"]
    assert pr_data["base_branch"] == "main"

    # 5. Check published PRs list
    resp_prs = client.get("/api/v1/publications/pull-requests")
    assert resp_prs.status_code == 200
    assert len(resp_prs.json()) == 1


def test_revoke_approval_api(pub_api_client):
    """Test revoking an approval before publication."""
    client, task_id, chain_id, patch_id, vrun_id = pub_api_client

    req_payload = {
        "task_id": task_id,
        "chain_id": chain_id,
        "patch_id": patch_id,
        "verification_run_id": vrun_id,
        "repo_owner": "owner",
        "repo_name": "repo",
        "target_base_branch": "main",
    }
    resp_req = client.post("/api/v1/publications/approvals/request", json=req_payload)
    approval_id = resp_req.json()["id"]

    revoke_payload = {"revoker_identity": "lead-reviewer", "reason": "Scope revised"}
    resp_rev = client.post(f"/api/v1/publications/approvals/{approval_id}/revoke", json=revoke_payload)
    assert resp_rev.status_code == 200
    assert resp_rev.json()["status"] == "CANCELLED"
    assert "Scope revised" in resp_rev.json()["invalidation_reason"]

    # Attempting to publish cancelled approval fails with 422
    resp_fail = client.post(f"/api/v1/publications/approvals/{approval_id}/publish", json={"require_real_sandbox": False})
    assert resp_fail.status_code == 422
