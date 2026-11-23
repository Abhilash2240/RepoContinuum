"""Publication workflow service orchestrating approval gates and PR publishing."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, TYPE_CHECKING
from repocontinuum.domain.planning import MaintenanceTask
from repocontinuum.domain.verification import EvidenceReport, Patch
from repocontinuum.github.approval import ApprovalValidationError, PublicationApprovalPolicy
from repocontinuum.github.models import (
    ApprovalStatus,
    PublicationApproval,
    PublicationRun,
    PublishedPullRequest,
)
from repocontinuum.github.publisher import BaseGitHubPublisher, GitHubBranchExistsError

if TYPE_CHECKING:
    from repocontinuum.persistence.repository import TaskChainRepository


class PublicationService:
    """Coordinates approval validation, branch publication, and PR creation."""

    def __init__(self, repository: TaskChainRepository, publisher: BaseGitHubPublisher) -> None:
        self.repo = repository
        self.publisher = publisher

    @staticmethod
    def generate_branch_name(task_id: str, patch_hash: str) -> str:
        """Create a sanitized, deterministic branch name."""
        clean_task = re.sub(r"[^a-zA-Z0-9_-]", "", task_id)[:12]
        clean_hash = re.sub(r"[^a-zA-Z0-9]", "", patch_hash)[:8]
        return f"repocontinuum/task-{clean_task}-{clean_hash}"

    def request_approval(
        self,
        task_id: str,
        chain_id: str,
        patch_id: str,
        verification_run_id: str,
        repo_owner: str,
        repo_name: str,
        target_base_branch: str = "main",
    ) -> PublicationApproval:
        """Create a new publication approval record in AWAITING_APPROVAL state."""
        patch = self.repo.get_patch(patch_id)
        if not patch:
            raise ValueError(f"Patch '{patch_id}' not found.")

        vrun = self.repo.get_verification_run(verification_run_id)
        if not vrun:
            raise ValueError(f"Verification run '{verification_run_id}' not found.")

        report = self.repo.get_evidence_report(verification_run_id)
        if not report:
            raise ValueError(f"Evidence report for verification run '{verification_run_id}' not found.")

        branch_name = self.generate_branch_name(task_id, patch.patch_hash)
        now_str = datetime.now(timezone.utc).isoformat()

        approval = PublicationApproval(
            id=f"appr-{uuid.uuid4().hex[:12]}",
            repository_owner=repo_owner,
            repository_name=repo_name,
            repository_id=f"{repo_owner}/{repo_name}",
            task_id=task_id,
            chain_id=chain_id,
            patch_id=patch_id,
            patch_hash=patch.patch_hash,
            base_commit_sha=patch.base_sha,
            target_base_branch=target_base_branch,
            proposed_head_branch=branch_name,
            verification_report_id=report.report_id,
            verification_run_id=verification_run_id,
            status=ApprovalStatus.AWAITING_APPROVAL,
            created_at=now_str,
        )
        return self.repo.save_publication_approval(approval)

    def grant_approval(
        self,
        approval_id: str,
        approver_identity: str,
        validity_hours: int = 24,
    ) -> PublicationApproval:
        """Explicit human signoff authorizing publication of the exact patch."""
        approval = self.repo.get_publication_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval '{approval_id}' not found.")

        if approval.status != ApprovalStatus.AWAITING_APPROVAL:
            raise ValueError(f"Cannot approve from state '{approval.status.value}'. Must be AWAITING_APPROVAL.")

        now = datetime.now(timezone.utc)
        approval.approver_identity = approver_identity
        approval.approved_at = now.isoformat()
        approval.expires_at = (now + timedelta(hours=validity_hours)).isoformat()
        approval.status = ApprovalStatus.APPROVED

        return self.repo.save_publication_approval(approval)

    def revoke_approval(self, approval_id: str, revoker: str, reason: str) -> PublicationApproval:
        """Revoke a previously granted approval."""
        approval = self.repo.get_publication_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval '{approval_id}' not found.")

        approval = PublicationApprovalPolicy.revoke_approval(approval, revoker, reason)
        return self.repo.save_publication_approval(approval)

    def generate_pr_content(
        self,
        task: MaintenanceTask,
        patch: Patch,
        report: EvidenceReport,
        head_sha: str,
        verification_run_id: str,
    ) -> Tuple[str, str]:
        """Generate structured title and markdown body for the pull request."""
        title = f"[RepoContinuum] {task.title}"

        # Verification check list
        checks_text = ""
        for c in report.checks_executed:
            cmd = " ".join(c.command) if isinstance(c.command, list) else str(c.command)
            checks_text += f"- **{c.name}**: `{c.status.value}` (command: `{cmd}`, exit code: {c.exit_code})\n"
        if not checks_text:
            checks_text = "- No individual checks recorded\n"

        # Obligations rechecked
        obligations_text = ""
        for ob in report.earlier_obligations_rechecked:
            obligations_text += f"- Obligation `{ob.obligation_id}`: `{ob.status.value}` (reason: {ob.message or 'Passed'})\n"
        if not obligations_text:
            obligations_text = "- No earlier active obligations required re-verification\n"

        # Regression text
        if report.regressions_detected:
            regression_text = f"⚠️ **REGRESSIONS DETECTED:** {', '.join(report.regressions_detected)}"
        else:
            regression_text = "✅ **Zero Regressions:** All earlier active obligations preserved intact."

        body = f"""## Summary
Automated maintenance patch proposed by RepoContinuum and authorized by human reviewer.

### Description
{task.description}

---

## Related Task
- **Task ID:** `{task.id}`
- **Task Chain ID:** `{task.chain_id}`

---

## Changed Files
{', '.join(f'`{f}`' for f in patch.changed_paths)}
- **Lines Added:** {patch.total_added_lines}
- **Lines Removed:** {patch.total_removed_lines}

---

## Verification Evidence
- **Verdict:** `{report.verification_conclusion.value}`
- **Execution Target:** `{report.sandbox_type.value}`
- **Execution Image:** `{report.execution_image}`
- **Image Digest:** `{report.execution_image_digest or 'local'}`

### Executed Checks
{checks_text}

### Earlier Obligations Rechecked
{obligations_text}

---

## Regression Status
{regression_text}

---

## Limitations & Unverified Conditions
- Verified in isolated disposable environment ({report.sandbox_type.value}).
- Automatic merging is disabled by policy. Review and merge must be completed manually.

---

## Reproducibility Metadata
- **Base Commit SHA:** `{patch.base_sha}`
- **Head Commit SHA:** `{head_sha}`
- **Patch Content Hash (SHA-256):** `{patch.patch_hash}`
- **Verification Run ID:** `{verification_run_id}`
"""
        return title, body.strip()

    def publish_approved_task(
        self,
        approval_id: str,
        require_real_sandbox: bool = False,
    ) -> PublishedPullRequest:
        """Execute the publication workflow for a validly approved patch."""
        approval = self.repo.get_publication_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval '{approval_id}' not found.")

        patch = self.repo.get_patch(approval.patch_id)
        if not patch:
            raise ValueError(f"Patch '{approval.patch_id}' not found.")

        task = self.repo.get_task(approval.task_id)
        if not task:
            raise ValueError(f"Task '{approval.task_id}' not found.")

        report = self.repo.get_evidence_report(approval.verification_run_id)

        # 1. State check: must be explicitly APPROVED
        if approval.status != ApprovalStatus.APPROVED:
            raise ApprovalValidationError(
                f"Publication rejected: Approval is not in APPROVED state (current state: {approval.status.value})"
            )

        # 2. Validate approval against current parameters
        is_valid, reason = PublicationApprovalPolicy.validate_for_publication(
            approval=approval,
            current_patch_hash=patch.patch_hash,
            current_base_sha=patch.base_sha,
            current_target_branch=approval.target_base_branch,
            verification_report=report,
            require_real_sandbox=require_real_sandbox,
        )
        if not is_valid:
            approval = PublicationApprovalPolicy.invalidate_approval(approval, reason or "Validation failed")
            self.repo.save_publication_approval(approval)
            raise ApprovalValidationError(f"Publication rejected: {reason}")

        # 2. Initialize publication run
        now_str = datetime.now(timezone.utc).isoformat()
        run = PublicationRun(
            id=f"pubrun-{uuid.uuid4().hex[:12]}",
            approval_id=approval.id,
            task_id=task.id,
            chain_id=task.chain_id,
            repository_owner=approval.repository_owner,
            repository_name=approval.repository_name,
            head_branch=approval.proposed_head_branch,
            base_branch=approval.target_base_branch,
            base_commit_sha=approval.base_commit_sha,
            status=ApprovalStatus.PUBLISHING,
            started_at=now_str,
        )
        self.repo.save_publication_run(run)

        # 3. Create branch or handle existing branch idempotently
        try:
            self.publisher.create_branch(
                owner=approval.repository_owner,
                repo=approval.repository_name,
                branch_name=approval.proposed_head_branch,
                base_sha=approval.base_commit_sha,
            )
        except GitHubBranchExistsError:
            # Idempotent continuation if branch exists
            pass
        except Exception as exc:
            run.status = ApprovalStatus.FAILED
            run.error_message = f"Failed to create branch: {exc}"
            run.completed_at = datetime.now(timezone.utc).isoformat()
            self.repo.save_publication_run(run)
            raise

        run.status = ApprovalStatus.BRANCH_CREATED
        self.repo.save_publication_run(run)

        # 4. Publish commit
        commit_message = f"fix({task.id}): {task.title}\n\nRepoContinuum task ID: {task.id}"
        try:
            head_sha = self.publisher.publish_commit(
                owner=approval.repository_owner,
                repo=approval.repository_name,
                branch_name=approval.proposed_head_branch,
                patch_content=patch.diff_content,
                commit_message=commit_message,
                base_commit_sha=approval.base_commit_sha,
            )
            run.head_commit_sha = head_sha
        except Exception as exc:
            run.status = ApprovalStatus.FAILED
            run.error_message = f"Failed to publish commit: {exc}"
            run.completed_at = datetime.now(timezone.utc).isoformat()
            self.repo.save_publication_run(run)
            raise

        # 5. Generate PR content and create pull request
        title, body = self.generate_pr_content(
            task=task,
            patch=patch,
            report=report,  # type: ignore
            head_sha=head_sha,
            verification_run_id=approval.verification_run_id,
        )

        try:
            pr = self.publisher.create_pull_request(
                owner=approval.repository_owner,
                repo=approval.repository_name,
                title=title,
                body=body,
                head_branch=approval.proposed_head_branch,
                base_branch=approval.target_base_branch,
                draft=False,
            )
        except Exception as exc:
            run.status = ApprovalStatus.FAILED
            run.error_message = f"Failed to create PR: {exc}"
            run.completed_at = datetime.now(timezone.utc).isoformat()
            self.repo.save_publication_run(run)
            raise

        # 6. Complete publication run and record published PR
        completed_at_str = datetime.now(timezone.utc).isoformat()
        run.pull_request_number = pr.number
        run.pull_request_url = pr.html_url
        run.status = ApprovalStatus.PR_CREATED
        run.completed_at = completed_at_str
        self.repo.save_publication_run(run)

        approval.status = ApprovalStatus.PR_CREATED
        self.repo.save_publication_approval(approval)

        published_pr = PublishedPullRequest(
            id=f"pubpr-{uuid.uuid4().hex[:12]}",
            run_id=run.id,
            approval_id=approval.id,
            repository_owner=approval.repository_owner,
            repository_name=approval.repository_name,
            pr_number=pr.number,
            html_url=pr.html_url,
            title=title,
            body=body,
            head_branch=approval.proposed_head_branch,
            base_branch=approval.target_base_branch,
            head_sha=head_sha,
            base_sha=approval.base_commit_sha,
            created_at=completed_at_str,
        )
        return self.repo.save_published_pull_request(published_pr)
