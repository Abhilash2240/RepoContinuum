"""End-to-end integration tests for Milestone 6 Approved PR Publishing."""

import pytest
from datetime import datetime, timezone
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
from repocontinuum.github.approval import ApprovalValidationError
from repocontinuum.github.models import ApprovalStatus
from repocontinuum.github.publication_service import PublicationService
from repocontinuum.github.publisher import FakeGitHubPublisher
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository


@pytest.fixture
def pub_e2e_setup(tmp_path):
    db_path = tmp_path / "pub_e2e.db"
    db = DatabaseManager(database_url=f"sqlite:///{db_path.as_posix()}")
    db.create_tables()
    repo = TaskChainRepository(db)
    publisher = FakeGitHubPublisher()
    service = PublicationService(repository=repo, publisher=publisher)

    chain = TaskChain(id="chn-e2e-1", repository_id="repocontinuum-org/demo-repo", title="E2E Chain")
    repo.save_chain(chain)

    task = MaintenanceTask(
        id="tsk-e2e-1",
        chain_id=chain.id,
        title="Fix high-frequency timestamp drift",
        description="Synchronize monotonic clock with monotonic_ns to avoid precision drift.",
    )
    repo.save_task(task)

    patch = Patch(
        id="pat-e2e-1",
        task_id=task.id,
        repository_id="repocontinuum-org/demo-repo",
        base_sha="d" * 40,
        patch_hash="9" * 64,
        changed_paths=["clock.py"],
        total_added_lines=4,
        total_removed_lines=1,
        diff_content="--- a/clock.py\n+++ b/clock.py\n@@ -1 +1 @@\n-time.time()\n+time.monotonic_ns()\n",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_patch(patch)

    vrun = VerificationRun(
        id="vrun-e2e-1",
        patch_id=patch.id,
        task_id=task.id,
        chain_id=chain.id,
        base_sha=patch.base_sha,
        workspace_id="ws-e2e",
        sandbox_type=SandboxType.FAKE,
        image_tag="python:3.13-slim",
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        status=VerificationRunStatus.COMPLETED,
    )
    repo.save_verification_run(vrun)

    report = EvidenceReport(
        report_id="evrep-e2e-1",
        repository_id="repocontinuum-org/demo-repo",
        chain_id=chain.id,
        task_id=task.id,
        base_sha=patch.base_sha,
        patch_id=patch.id,
        patch_hash=patch.patch_hash,
        changed_files=patch.changed_paths,
        added_lines_count=patch.total_added_lines,
        removed_lines_count=patch.total_removed_lines,
        workspace_id="ws-e2e",
        sandbox_type=SandboxType.FAKE,
        execution_image="python:3.13-slim",
        execution_image_digest=None,
        checks_executed=[
            VerificationCheck(
                id="chk-1",
                name="test_clock_drift",
                command=["pytest", "tests/test_clock.py"],
                status=CheckStatus.PASSED,
                exit_code=0,
                duration_ms=25,
            )
        ],
        earlier_obligations_rechecked=[],
        regressions_detected=[],
        skipped_or_unsupported_checks=[],
        outstanding_risks=[],
        verification_conclusion=CheckStatus.PASSED,
        summary_markdown="# Verification Summary\nAll checks passed.",
    )
    repo.save_evidence_report(report, run_id=vrun.id)

    return {
        "service": service,
        "repo": repo,
        "publisher": publisher,
        "task": task,
        "chain": chain,
        "patch": patch,
        "vrun": vrun,
        "report": report,
    }


def test_complete_approved_publication_workflow(pub_e2e_setup):
    """Test full publication flow: request -> approve -> publish -> idempotent recovery."""
    service = pub_e2e_setup["service"]
    repo = pub_e2e_setup["repo"]
    publisher = pub_e2e_setup["publisher"]
    task = pub_e2e_setup["task"]
    chain = pub_e2e_setup["chain"]
    patch = pub_e2e_setup["patch"]
    vrun = pub_e2e_setup["vrun"]

    # 1. Request Approval
    approval = service.request_approval(
        task_id=task.id,
        chain_id=chain.id,
        patch_id=patch.id,
        verification_run_id=vrun.id,
        repo_owner="repocontinuum-org",
        repo_name="demo-repo",
        target_base_branch="main",
    )
    assert approval.status == ApprovalStatus.AWAITING_APPROVAL
    assert approval.patch_hash == patch.patch_hash
    assert "repocontinuum/task-" in approval.proposed_head_branch

    # 2. Cannot publish without human approval
    with pytest.raises(ApprovalValidationError, match="not in APPROVED state"):
        service.publish_approved_task(approval.id)

    # 3. Grant Human Approval
    approved = service.grant_approval(
        approval_id=approval.id,
        approver_identity="lead-engineer@repocontinuum.org",
        validity_hours=48,
    )
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.approver_identity == "lead-engineer@repocontinuum.org"

    # 4. Tamper with patch hash -> should invalidate approval
    tampered_patch = patch.model_copy(update={"patch_hash": "0" * 64})
    repo.save_patch(tampered_patch)

    with pytest.raises(ApprovalValidationError, match="Patch content hash mismatch"):
        service.publish_approved_task(approval.id)

    # Verify approval state was updated to INVALIDATED
    stale_appr = repo.get_publication_approval(approval.id)
    assert stale_appr.status == ApprovalStatus.INVALIDATED
    assert "mismatch" in stale_appr.invalidation_reason

    # Restore patch and re-approve
    repo.save_patch(patch)
    reapproved = stale_appr.model_copy(update={"status": ApprovalStatus.APPROVED, "invalidation_reason": None})
    repo.save_publication_approval(reapproved)

    # 5. Genuine publication
    published_pr = service.publish_approved_task(approval.id)
    assert published_pr.pr_number == 101
    assert published_pr.head_branch == approval.proposed_head_branch
    assert published_pr.base_branch == "main"
    assert "https://github.com/repocontinuum-org/demo-repo/pull/101" in published_pr.html_url

    # Check that PR content contains structured sections
    assert "## Summary" in published_pr.body
    assert "## Verification Evidence" in published_pr.body
    assert "## Regression Status" in published_pr.body
    assert "## Reproducibility Metadata" in published_pr.body
    assert published_pr.base_sha == patch.base_sha

    # 6. Verify database records
    runs = repo.list_publication_runs(approval.id)
    assert len(runs) == 1
    assert runs[0].status == ApprovalStatus.PR_CREATED

    stored_prs = repo.list_published_pull_requests()
    assert len(stored_prs) == 1
    assert stored_prs[0].pr_number == 101

    # 7. Idempotent re-publication (duplicate attempt returns existing PR without crashing)
    # Stale_appr is now PR_CREATED, re-approving for duplicate test:
    stale_appr.status = ApprovalStatus.APPROVED
    repo.save_publication_approval(stale_appr)

    pr_republish = service.publish_approved_task(approval.id)
    assert pr_republish.pr_number == 101
