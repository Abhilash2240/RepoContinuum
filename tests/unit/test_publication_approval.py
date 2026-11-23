"""Unit tests for publication approval policy and invalidation gates."""

import pytest
from datetime import datetime, timezone, timedelta
from repocontinuum.domain.verification import (
    CheckStatus,
    EvidenceReport,
    SandboxType,
    VerificationCheck,
    VerificationRunStatus,
)
from repocontinuum.github.approval import PublicationApprovalPolicy
from repocontinuum.github.models import ApprovalStatus, PublicationApproval


@pytest.fixture
def sample_report():
    return EvidenceReport(
        report_id="evrep-101",
        repository_id="test-org/test-repo",
        chain_id="chain-1",
        task_id="task-1",
        base_sha="a" * 40,
        patch_id="pat-1",
        patch_hash="f" * 64,
        changed_files=["app.py"],
        added_lines_count=5,
        removed_lines_count=1,
        workspace_id="ws-1",
        sandbox_type=SandboxType.FAKE,
        execution_image="python:3.13-slim",
        execution_image_digest=None,
        status=VerificationRunStatus.COMPLETED,
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


@pytest.fixture
def approved_record():
    now = datetime.now(timezone.utc)
    return PublicationApproval(
        id="appr-1",
        repository_owner="test-org",
        repository_name="test-repo",
        repository_id="test-org/test-repo",
        task_id="task-1",
        chain_id="chain-1",
        patch_id="pat-1",
        patch_hash="f" * 64,
        base_commit_sha="a" * 40,
        target_base_branch="main",
        proposed_head_branch="repocontinuum/task-1-f8a9",
        verification_report_id="evrep-101",
        verification_run_id="vrun-101",
        approver_identity="lead-architect",
        status=ApprovalStatus.APPROVED,
        created_at=now.isoformat(),
        approved_at=now.isoformat(),
        expires_at=(now + timedelta(hours=24)).isoformat(),
    )


def test_approval_validates_when_all_invariants_match(approved_record, sample_report):
    """Verify approval succeeds when patch hash, base SHA, and report match."""
    is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
        approval=approved_record,
        current_patch_hash="f" * 64,
        current_base_sha="a" * 40,
        current_target_branch="main",
        verification_report=sample_report,
    )
    assert is_valid is True
    assert reason is None


def test_approval_rejected_if_patch_hash_tampered(approved_record, sample_report):
    """Verify approval rejects if current patch hash doesn't match approved hash."""
    is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
        approval=approved_record,
        current_patch_hash="e" * 64,  # Tampered patch hash
        current_base_sha="a" * 40,
        current_target_branch="main",
        verification_report=sample_report,
    )
    assert is_valid is False
    assert "Patch content hash mismatch" in reason


def test_approval_rejected_if_base_sha_changed(approved_record, sample_report):
    """Verify approval rejects if base commit SHA moved."""
    is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
        approval=approved_record,
        current_patch_hash="f" * 64,
        current_base_sha="b" * 40,  # Changed base SHA
        current_target_branch="main",
        verification_report=sample_report,
    )
    assert is_valid is False
    assert "Base commit SHA mismatch" in reason


def test_approval_rejected_if_target_branch_changed(approved_record, sample_report):
    """Verify approval rejects if target branch differs."""
    is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
        approval=approved_record,
        current_patch_hash="f" * 64,
        current_base_sha="a" * 40,
        current_target_branch="release-v2",  # Changed branch
        verification_report=sample_report,
    )
    assert is_valid is False
    assert "Target branch mismatch" in reason


def test_approval_rejected_if_verification_report_has_regressions(approved_record, sample_report):
    """Verify approval rejects if verification report contains regression alerts."""
    reg_report = sample_report.model_copy(update={"regressions_detected": ["ob-prior-1"]})
    is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
        approval=approved_record,
        current_patch_hash="f" * 64,
        current_base_sha="a" * 40,
        current_target_branch="main",
        verification_report=reg_report,
    )
    assert is_valid is False
    assert "contains 1 regressions" in reason


def test_approval_rejected_if_expired(approved_record, sample_report):
    """Verify approval rejects if expiration timestamp has passed."""
    expired_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    approved_record.expires_at = expired_time

    is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
        approval=approved_record,
        current_patch_hash="f" * 64,
        current_base_sha="a" * 40,
        current_target_branch="main",
        verification_report=sample_report,
    )
    assert is_valid is False
    assert "Approval has expired" in reason


def test_approval_invalidation_and_revocation(approved_record):
    """Test explicit invalidation and revocation functions."""
    PublicationApprovalPolicy.invalidate_approval(approved_record, "Base SHA diverged upstream")
    assert approved_record.status == ApprovalStatus.INVALIDATED
    assert approved_record.invalidation_reason == "Base SHA diverged upstream"

    PublicationApprovalPolicy.revoke_approval(approved_record, "reviewer-bob", "Requirements changed")
    assert approved_record.status == ApprovalStatus.CANCELLED
    assert "Revoked by reviewer-bob" in approved_record.invalidation_reason
