"""Verification pipeline orchestrating patch application, sandbox execution, and regression checking."""

from __future__ import annotations

import datetime
import uuid
from pathlib import Path
from typing import List, Optional

from repocontinuum.domain.planning import MaintenanceTask, Obligation, ObligationStatus
from repocontinuum.domain.verification import (
    CheckStatus,
    EvidenceReport,
    ObligationRecheckResult,
    Patch,
    PatchStatus,
    SandboxType,
    VerificationCheck,
    VerificationRun,
    VerificationRunStatus,
)
from repocontinuum.execution.allowlist import SecretRedactor
from repocontinuum.execution.sandbox import (
    BaseSandboxRunner,
    DockerSandboxRunner,
    FakeSandboxRunner,
)
from repocontinuum.execution.workspace import DisposableWorkspaceManager
from repocontinuum.patching.applier import UnifiedDiffApplier
from repocontinuum.patching.diff_parser import UnifiedDiffParser
from repocontinuum.patching.security import PatchSecurityValidator


class VerificationEngine:
    """End-to-end verification engine for patch application, sandbox checks, and regression gates."""

    def __init__(self, sandbox_runner: Optional[BaseSandboxRunner] = None):
        self.sandbox_runner = sandbox_runner or DockerSandboxRunner()

    def verify_patch(
        self,
        repo_path: Path,
        task: MaintenanceTask,
        patch: Patch,
        earlier_active_obligations: List[Obligation],
        check_commands: Optional[List[List[str]]] = None,
    ) -> tuple[VerificationRun, EvidenceReport]:
        """Execute the full isolated verification pipeline on a patch."""
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        run_id = f"vrun-{uuid.uuid4().hex[:12]}"
        report_id = f"evrep-{uuid.uuid4().hex[:12]}"

        # Determine sandbox type
        sandbox_type = SandboxType.DOCKER if isinstance(self.sandbox_runner, DockerSandboxRunner) else SandboxType.FAKE
        image_tag = getattr(self.sandbox_runner, "image_tag", "python:3.13-slim")

        checks_executed: List[VerificationCheck] = []
        obligation_rechecks: List[ObligationRecheckResult] = []
        regressions_detected: List[str] = []
        skipped_or_unsupported: List[str] = []
        outstanding_risks: List[str] = []

        workspace = None
        try:
            # Step 1: Parse and validate patch syntax and content hash
            file_diffs = UnifiedDiffParser.parse(patch.diff_content)
            computed_hash = UnifiedDiffParser.compute_patch_hash(patch.diff_content)
            if computed_hash != patch.patch_hash:
                raise ValueError(
                    f"Patch content hash mismatch: recorded '{patch.patch_hash}', computed '{computed_hash}'"
                )

            # Step 2: Path security and traversal checks
            changed_paths = PatchSecurityValidator.validate_patch_security(file_diffs)

            # Step 3: Create isolated disposable working copy
            workspace = DisposableWorkspaceManager.create_workspace(
                repo_path=repo_path,
                expected_base_sha=patch.base_sha,
                repository_id=patch.repository_id,
            )

            # Step 4: Apply patch in disposable workspace
            UnifiedDiffApplier.apply_diffs(file_diffs, workspace.path)

            # Step 5: Execute primary configured checks in the sandbox
            commands_to_run = check_commands or [["python", "-m", "py_compile"]]

            all_passed = True
            for cmd_idx, cmd in enumerate(commands_to_run, start=1):
                # If command is incomplete py_compile without files, append changed python files
                full_cmd = list(cmd)
                if full_cmd == ["python", "-m", "py_compile"]:
                    py_files = [p for p in changed_paths if p.endswith((".py", ".pyi"))]
                    if py_files:
                        full_cmd.extend(py_files)
                    else:
                        full_cmd.append(".")

                check_id = f"chk-{run_id}-{cmd_idx}"
                cmd_name = " ".join(full_cmd[:3])

                result = self.sandbox_runner.run(full_cmd, workspace.path)
                check_record = VerificationCheck(
                    id=check_id,
                    name=cmd_name,
                    command=full_cmd,
                    status=result.status,
                    exit_code=result.exit_code,
                    duration_ms=result.duration_ms,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    executed_in_sandbox=result.executed_in_sandbox,
                    message=result.message,
                )
                checks_executed.append(check_record)

                if result.status != CheckStatus.PASSED:
                    all_passed = False
                    if result.status in {CheckStatus.SKIPPED, CheckStatus.NOT_RUN, CheckStatus.INCONCLUSIVE}:
                        skipped_or_unsupported.append(f"Check '{cmd_name}': {result.status.value} - {result.message}")

            # Step 6: Re-run earlier active obligations to detect regressions
            active_earlier = [o for o in earlier_active_obligations if o.status == ObligationStatus.ACTIVE and o.source_task_id != task.id]

            for ob in active_earlier:
                if ob.verifier_ref and (ob.verifier_ref.endswith(".py") or ":" in ob.verifier_ref):
                    # Executable test verifier available
                    test_target = ob.verifier_ref.split(":", 1)[0]
                    recheck_cmd = ["python", "-m", "pytest", test_target]
                    res = self.sandbox_runner.run(recheck_cmd, workspace.path)

                    is_reg = (res.status == CheckStatus.FAILED)
                    if is_reg:
                        regressions_detected.append(
                            f"Obligation '{ob.id}' ({ob.description}) broke after applying changes for Task '{task.id}'"
                        )

                    obligation_rechecks.append(
                        ObligationRecheckResult(
                            obligation_id=ob.id,
                            source_task_id=ob.source_task_id,
                            description=ob.description,
                            verifier_ref=ob.verifier_ref,
                            status=res.status,
                            is_regression=is_reg,
                            message=res.message or f"Rechecked with {recheck_cmd[0]} {recheck_cmd[1]}",
                        )
                    )
                else:
                    # Inconclusive or no executable verifier
                    obligation_rechecks.append(
                        ObligationRecheckResult(
                            obligation_id=ob.id,
                            source_task_id=ob.source_task_id,
                            description=ob.description,
                            verifier_ref=ob.verifier_ref,
                            status=CheckStatus.INCONCLUSIVE,
                            is_regression=False,
                            message="No executable test verifier declared for obligation.",
                        )
                    )
                    skipped_or_unsupported.append(f"Obligation '{ob.id}': no executable verifier declared.")

            # Step 7: Determine overall verification run status
            has_regressions = len(regressions_detected) > 0

            if has_regressions:
                overall_run_status = VerificationRunStatus.REGRESSION_DETECTED
                conclusion = CheckStatus.FAILED
            elif not all_passed:
                overall_run_status = VerificationRunStatus.FAILED
                conclusion = CheckStatus.FAILED
            else:
                overall_run_status = VerificationRunStatus.COMPLETED
                conclusion = CheckStatus.PASSED

            if not self.sandbox_runner.is_available():
                conclusion = CheckStatus.NOT_RUN
                overall_run_status = VerificationRunStatus.FAILED

        except Exception as ex:
            overall_run_status = VerificationRunStatus.FAILED
            conclusion = CheckStatus.FAILED
            outstanding_risks.append(f"Verification pipeline failed: {ex}")
            has_regressions = False

        finally:
            # Deterministic workspace cleanup
            if workspace:
                workspace.cleanup()

        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Build VerificationRun model
        vrun = VerificationRun(
            id=run_id,
            patch_id=patch.id,
            task_id=task.id,
            chain_id=task.chain_id,
            base_sha=patch.base_sha,
            workspace_id=workspace.metadata.workspace_id if workspace else "none",
            sandbox_type=sandbox_type,
            image_tag=image_tag,
            image_digest=None,
            started_at=started_at,
            completed_at=completed_at,
            status=overall_run_status,
            checks=checks_executed,
            obligation_rechecks=obligation_rechecks,
            has_regressions=has_regressions,
        )

        # Build Markdown summary for EvidenceReport
        summary_md = self._render_summary_markdown(vrun, patch, task, conclusion, regressions_detected)

        # Build EvidenceReport model
        report = EvidenceReport(
            report_id=report_id,
            repository_id=patch.repository_id,
            chain_id=task.chain_id,
            task_id=task.id,
            base_sha=patch.base_sha,
            patch_id=patch.id,
            patch_hash=patch.patch_hash,
            changed_files=patch.changed_paths,
            added_lines_count=patch.total_added_lines,
            removed_lines_count=patch.total_removed_lines,
            workspace_id=workspace.metadata.workspace_id if workspace else "none",
            execution_image=image_tag,
            execution_image_digest=None,
            sandbox_type=sandbox_type,
            checks_executed=checks_executed,
            earlier_obligations_rechecked=obligation_rechecks,
            regressions_detected=regressions_detected,
            skipped_or_unsupported_checks=skipped_or_unsupported,
            outstanding_risks=outstanding_risks,
            verification_conclusion=conclusion,
            summary_markdown=summary_md,
            generated_at=completed_at,
        )

        return vrun, report

    @staticmethod
    def _render_summary_markdown(
        vrun: VerificationRun,
        patch: Patch,
        task: MaintenanceTask,
        conclusion: CheckStatus,
        regressions: List[str],
    ) -> str:
        """Render readable markdown summary for evidence reports."""
        lines = [
            f"# Verification Evidence Report — {vrun.id}",
            f"- **Task:** {task.id} ({task.title})",
            f"- **Base Commit SHA:** `{patch.base_sha}`",
            f"- **Patch Hash (SHA-256):** `{patch.patch_hash}`",
            f"- **Verification Conclusion:** **{conclusion.value}**",
            f"- **Sandbox Mode:** `{vrun.sandbox_type.value}` ({vrun.image_tag})",
            "",
            "## Executed Checks",
        ]
        for c in vrun.checks:
            lines.append(f"- **{c.name}**: `{c.status.value}` (exit code {c.exit_code}, {c.duration_ms}ms)")

        lines.append("")
        lines.append("## Earlier Obligations Re-verified")
        if not vrun.obligation_rechecks:
            lines.append("- *No earlier active obligations to re-check.*")
        else:
            for o in vrun.obligation_rechecks:
                reg_marker = " ⚠️ [REGRESSION]" if o.is_regression else ""
                lines.append(f"- `{o.status.value}`: {o.description}{reg_marker} (ref: `{o.verifier_ref}`)")

        if regressions:
            lines.append("")
            lines.append("## ⚠️ Detected Regressions")
            for r in regressions:
                lines.append(f"- {r}")

        return "\n".join(lines)
