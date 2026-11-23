"""Approval-bound publication policy and invalidation engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple
from repocontinuum.domain.verification import CheckStatus, EvidenceReport
from repocontinuum.github.models import ApprovalStatus, PublicationApproval


class ApprovalValidationError(Exception):
    """Raised when an approval is invalid, stale, revoked, or fails integrity checks."""
    pass


class PublicationApprovalPolicy:
    """Enforces strict cryptographic and contextual binding for publication approvals."""

    @staticmethod
    def validate_for_publication(
        approval: PublicationApproval,
        current_patch_hash: str,
        current_base_sha: str,
        current_target_branch: str,
        verification_report: Optional[EvidenceReport] = None,
        require_real_sandbox: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """Validate that an approval is active and matches all invariant parameters.

        Returns (is_valid, invalidation_reason).
        """
        # 1. State check
        if approval.status != ApprovalStatus.APPROVED:
            return False, f"Approval is not in APPROVED state (current state: {approval.status.value})"

        # 2. Expiration check
        if approval.expires_at:
            now = datetime.now(timezone.utc)
            try:
                exp = datetime.fromisoformat(approval.expires_at.replace("Z", "+00:00"))
                if now > exp:
                    return False, "Approval has expired"
            except Exception:
                return False, "Malformed approval expiration timestamp"

        # 3. Patch hash binding
        if approval.patch_hash.lower() != current_patch_hash.lower():
            return False, (
                f"Patch content hash mismatch. Approved: {approval.patch_hash[:12]}..., "
                f"Current: {current_patch_hash[:12]}..."
            )

        # 4. Base commit SHA binding
        if approval.base_commit_sha.lower() != current_base_sha.lower():
            return False, (
                f"Base commit SHA mismatch. Approved: {approval.base_commit_sha[:12]}..., "
                f"Current: {current_base_sha[:12]}..."
            )

        # 5. Target branch binding
        if approval.target_base_branch != current_target_branch:
            return False, (
                f"Target branch mismatch. Approved: '{approval.target_base_branch}', "
                f"Current: '{current_target_branch}'"
            )

        # 6. Verification report validity
        if not verification_report:
            return False, "No verification evidence report associated with this approval"

        if verification_report.report_id != approval.verification_report_id:
            return False, (
                f"Verification report mismatch. Approved: '{approval.verification_report_id}', "
                f"Current: '{verification_report.report_id}'"
            )

        # Report must conclude PASSED
        if verification_report.verification_conclusion != CheckStatus.PASSED:
            return False, (
                f"Verification conclusion is not PASSED (verdict: {verification_report.verification_conclusion.value})"
            )

        # Must have zero regressions detected
        if verification_report.regressions_detected:
            return False, f"Verification report contains {len(verification_report.regressions_detected)} regressions"

        # Docker release gate check: if real sandbox is required, ensure it wasn't a fake sandbox run
        if require_real_sandbox:
            from repocontinuum.domain.verification import SandboxType
            if verification_report.sandbox_type != SandboxType.DOCKER:
                return False, (
                    f"Publication policy requires real Docker container verification; "
                    f"run used {verification_report.sandbox_type.value}"
                )

        return True, None

    @staticmethod
    def invalidate_approval(approval: PublicationApproval, reason: str) -> PublicationApproval:
        """Mark an approval record as invalidated with an explicit reason."""
        approval.status = ApprovalStatus.INVALIDATED
        approval.invalidation_reason = reason
        return approval

    @staticmethod
    def revoke_approval(approval: PublicationApproval, revoker: str, reason: str) -> PublicationApproval:
        """Revoke an approval before publication."""
        approval.status = ApprovalStatus.CANCELLED
        approval.invalidation_reason = f"Revoked by {revoker}: {reason}"
        return approval
