"""Repository pattern implementation for durable persistence of task chains, patches, and verification."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from repocontinuum.domain.agent import (
    AgentRun,
    AgentRunStatus,
)
from repocontinuum.domain.planning import (
    ActorType,
    AuditEvent,
    ChainStatus,
    Checkpoint,
    DependencySource,
    MaintenanceTask,
    Obligation,
    ObligationStatus,
    TaskChain,
    TaskDependency,
    TaskStatus,
)
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
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.tables import (
    AgentRunTable,
    AuditEventTable,
    BenchmarkRunTable,
    CheckpointTable,
    EvidenceReportTable,
    GitHubWebhookDeliveryTable,
    MaintenanceTaskTable,
    ObligationTable,
    PatchTable,
    PublicationApprovalTable,
    PublicationRunTable,
    PublishedPullRequestTable,
    TaskChainTable,
    TaskDependencyTable,
    VerificationRunTable,
)
from repocontinuum.github.models import (
    ApprovalStatus,
    PublicationApproval,
    PublicationRun,
    PublishedPullRequest,
)


class TaskChainRepository:
    """Provides atomic query and mutation methods for the task chain and verification domain."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    # ---------------- Task Chains ----------------

    def save_chain(self, chain: TaskChain) -> TaskChain:
        """Create or update a task chain."""
        with self.db.session_scope() as session:
            existing = session.get(TaskChainTable, chain.id)
            if existing:
                existing.title = chain.title
                existing.description = chain.description
                existing.status = chain.status.value
                existing.updated_at = chain.updated_at
            else:
                record = TaskChainTable(
                    id=chain.id,
                    repository_id=chain.repository_id,
                    title=chain.title,
                    description=chain.description,
                    status=chain.status.value,
                    created_at=chain.created_at,
                    updated_at=chain.updated_at,
                )
                session.add(record)
        return chain

    def get_chain(self, chain_id: str) -> Optional[TaskChain]:
        """Retrieve a task chain by ID."""
        with self.db.session_scope() as session:
            record = session.get(TaskChainTable, chain_id)
            if not record:
                return None
            return TaskChain(
                id=record.id,
                repository_id=record.repository_id,
                title=record.title,
                description=record.description,
                status=ChainStatus(record.status),
                created_at=record.created_at,
                updated_at=record.updated_at,
            )

    def list_chains(self) -> List[TaskChain]:
        """List all stored task chains."""
        with self.db.session_scope() as session:
            stmt = select(TaskChainTable).order_by(TaskChainTable.created_at.desc())
            records = session.scalars(stmt).all()
            return [
                TaskChain(
                    id=r.id,
                    repository_id=r.repository_id,
                    title=r.title,
                    description=r.description,
                    status=ChainStatus(r.status),
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in records
            ]

    # ---------------- Maintenance Tasks ----------------

    def save_task(self, task: MaintenanceTask) -> MaintenanceTask:
        """Create or update a maintenance task."""
        with self.db.session_scope() as session:
            existing = session.get(MaintenanceTaskTable, task.id)
            if existing:
                existing.title = task.title
                existing.description = task.description
                existing.order_index = task.order_index
                existing.status = task.status.value
                existing.acceptance_criteria = task.acceptance_criteria
                existing.candidate_files = task.candidate_files
                existing.candidate_symbols = task.candidate_symbols
                existing.updated_at = task.updated_at
            else:
                record = MaintenanceTaskTable(
                    id=task.id,
                    chain_id=task.chain_id,
                    title=task.title,
                    description=task.description,
                    order_index=task.order_index,
                    status=task.status.value,
                    acceptance_criteria=task.acceptance_criteria,
                    candidate_files=task.candidate_files,
                    candidate_symbols=task.candidate_symbols,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
                session.add(record)
        return task

    def get_task(self, task_id: str) -> Optional[MaintenanceTask]:
        """Retrieve an individual task by ID."""
        with self.db.session_scope() as session:
            record = session.get(MaintenanceTaskTable, task_id)
            if not record:
                return None
            return self._to_task_model(record)

    def get_tasks_for_chain(self, chain_id: str) -> List[MaintenanceTask]:
        """Retrieve all tasks in a chain ordered by order_index."""
        with self.db.session_scope() as session:
            stmt = (
                select(MaintenanceTaskTable)
                .where(MaintenanceTaskTable.chain_id == chain_id)
                .order_by(MaintenanceTaskTable.order_index)
            )
            records = session.scalars(stmt).all()
            return [self._to_task_model(r) for r in records]

    # ---------------- Task Dependencies ----------------

    def add_dependency(self, dep: TaskDependency) -> TaskDependency:
        """Store a task dependency edge."""
        with self.db.session_scope() as session:
            stmt = select(TaskDependencyTable).where(
                TaskDependencyTable.chain_id == dep.chain_id,
                TaskDependencyTable.predecessor_task_id == dep.predecessor_task_id,
                TaskDependencyTable.successor_task_id == dep.successor_task_id,
            )
            existing = session.scalars(stmt).first()
            if not existing:
                record = TaskDependencyTable(
                    id=dep.id,
                    chain_id=dep.chain_id,
                    predecessor_task_id=dep.predecessor_task_id,
                    successor_task_id=dep.successor_task_id,
                    source=dep.source.value,
                    approved_by=dep.approved_by,
                    created_at=dep.created_at,
                )
                session.add(record)
        return dep

    def get_dependencies_for_chain(self, chain_id: str) -> List[TaskDependency]:
        """Retrieve all task dependencies for a given chain."""
        with self.db.session_scope() as session:
            stmt = select(TaskDependencyTable).where(TaskDependencyTable.chain_id == chain_id)
            records = session.scalars(stmt).all()
            return [
                TaskDependency(
                    id=r.id,
                    chain_id=r.chain_id,
                    predecessor_task_id=r.predecessor_task_id,
                    successor_task_id=r.successor_task_id,
                    source=DependencySource(r.source),
                    approved_by=r.approved_by,
                    created_at=r.created_at,
                )
                for r in records
            ]

    # ---------------- Obligations ----------------

    def save_obligation(self, obligation: Obligation) -> Obligation:
        """Create or update an obligation."""
        with self.db.session_scope() as session:
            existing = session.get(ObligationTable, obligation.id)
            if existing:
                existing.description = obligation.description
                existing.status = obligation.status.value
                existing.verifier_ref = obligation.verifier_ref
                existing.status_reason = obligation.status_reason
                existing.updated_at = obligation.updated_at
            else:
                record = ObligationTable(
                    id=obligation.id,
                    chain_id=obligation.chain_id,
                    source_task_id=obligation.source_task_id,
                    description=obligation.description,
                    status=obligation.status.value,
                    verifier_ref=obligation.verifier_ref,
                    status_reason=obligation.status_reason,
                    created_at=obligation.created_at,
                    updated_at=obligation.updated_at,
                )
                session.add(record)
        return obligation

    def get_obligation(self, obligation_id: str) -> Optional[Obligation]:
        """Retrieve an obligation by ID."""
        with self.db.session_scope() as session:
            record = session.get(ObligationTable, obligation_id)
            if not record:
                return None
            return self._to_obligation_model(record)

    def get_obligations_for_chain(self, chain_id: str) -> List[Obligation]:
        """Retrieve all obligations registered for a chain."""
        with self.db.session_scope() as session:
            stmt = (
                select(ObligationTable)
                .where(ObligationTable.chain_id == chain_id)
                .order_by(ObligationTable.created_at)
            )
            records = session.scalars(stmt).all()
            return [self._to_obligation_model(r) for r in records]

    # ---------------- Patches ----------------

    def save_patch(self, patch: Patch) -> Patch:
        """Create or update a patch record."""
        with self.db.session_scope() as session:
            existing = session.get(PatchTable, patch.id)
            if existing:
                existing.status = patch.status.value
                existing.patch_hash = patch.patch_hash
                existing.diff_content = patch.diff_content
                existing.changed_paths = patch.changed_paths
                existing.total_added_lines = patch.total_added_lines
                existing.total_removed_lines = patch.total_removed_lines
            else:
                record = PatchTable(
                    id=patch.id,
                    repository_id=patch.repository_id,
                    task_id=patch.task_id,
                    base_sha=patch.base_sha,
                    patch_hash=patch.patch_hash,
                    diff_content=patch.diff_content,
                    changed_paths=patch.changed_paths,
                    total_added_lines=patch.total_added_lines,
                    total_removed_lines=patch.total_removed_lines,
                    status=patch.status.value,
                    created_at=patch.created_at,
                )
                session.add(record)
        return patch

    def get_patch(self, patch_id: str) -> Optional[Patch]:
        """Retrieve a patch by ID."""
        with self.db.session_scope() as session:
            record = session.get(PatchTable, patch_id)
            if not record:
                return None
            return Patch(
                id=record.id,
                repository_id=record.repository_id,
                task_id=record.task_id,
                base_sha=record.base_sha,
                patch_hash=record.patch_hash,
                diff_content=record.diff_content,
                changed_paths=list(record.changed_paths or []),
                total_added_lines=record.total_added_lines,
                total_removed_lines=record.total_removed_lines,
                status=PatchStatus(record.status),
                created_at=record.created_at,
            )

    # ---------------- Verification Runs & Evidence Reports ----------------

    def save_verification_run(self, vrun: VerificationRun) -> VerificationRun:
        """Persist a verification run."""
        with self.db.session_scope() as session:
            record = VerificationRunTable(
                id=vrun.id,
                patch_id=vrun.patch_id,
                task_id=vrun.task_id,
                chain_id=vrun.chain_id,
                base_sha=vrun.base_sha,
                workspace_id=vrun.workspace_id,
                sandbox_type=vrun.sandbox_type.value,
                image_tag=vrun.image_tag,
                image_digest=vrun.image_digest,
                started_at=vrun.started_at,
                completed_at=vrun.completed_at,
                status=vrun.status.value,
                checks_json=[c.model_dump() for c in vrun.checks],
                obligation_rechecks_json=[o.model_dump() for o in vrun.obligation_rechecks],
                has_regressions=vrun.has_regressions,
            )
            session.add(record)
        return vrun

    def get_verification_run(self, run_id: str) -> Optional[VerificationRun]:
        """Retrieve a verification run by ID."""
        with self.db.session_scope() as session:
            record = session.get(VerificationRunTable, run_id)
            if not record:
                return None
            checks = [VerificationCheck.model_validate(c) for c in (record.checks_json or [])]
            rechecks = [ObligationRecheckResult.model_validate(o) for o in (record.obligation_rechecks_json or [])]
            return VerificationRun(
                id=record.id,
                patch_id=record.patch_id,
                task_id=record.task_id,
                chain_id=record.chain_id,
                base_sha=record.base_sha,
                workspace_id=record.workspace_id,
                sandbox_type=SandboxType(record.sandbox_type),
                image_tag=record.image_tag,
                image_digest=record.image_digest,
                started_at=record.started_at,
                completed_at=record.completed_at,
                status=VerificationRunStatus(record.status),
                checks=checks,
                obligation_rechecks=rechecks,
                has_regressions=record.has_regressions,
            )

    def save_evidence_report(self, report: EvidenceReport, run_id: Optional[str] = None) -> EvidenceReport:
        """Persist a generated evidence report."""
        with self.db.session_scope() as session:
            record = EvidenceReportTable(
                id=report.report_id,
                verification_run_id=run_id or report.report_id,
                report_json=report.model_dump(),
                summary_markdown=report.summary_markdown,
                generated_at=report.generated_at,
            )
            session.add(record)
        return report

    def get_evidence_report(self, report_or_run_id: str) -> Optional[EvidenceReport]:
        """Retrieve a persisted evidence report by report ID or verification run ID."""
        with self.db.session_scope() as session:
            record = session.get(EvidenceReportTable, report_or_run_id)
            if not record:
                stmt = select(EvidenceReportTable).where(
                    EvidenceReportTable.verification_run_id == report_or_run_id
                )
                record = session.scalars(stmt).first()
            if not record:
                return None
            return EvidenceReport.model_validate(record.report_json)

    # ---------------- Agent Runs ----------------

    def save_agent_run(self, agent_run: AgentRun) -> AgentRun:
        """Create or update a persisted agent run record."""
        with self.db.session_scope() as session:
            record = session.get(AgentRunTable, agent_run.id)
            if not record:
                record = AgentRunTable(
                    id=agent_run.id,
                    chain_id=agent_run.chain_id,
                    task_id=agent_run.task_id,
                    provider=agent_run.provider,
                    model=agent_run.model,
                    status=agent_run.status.value,
                    prompt_hash=agent_run.prompt_hash,
                    prompt_version=agent_run.prompt_version,
                    attempt_number=agent_run.attempt_number,
                    max_repair_attempts=agent_run.max_repair_attempts,
                    tool_calls_json=agent_run.tool_calls,
                    prompt_tokens=agent_run.prompt_tokens,
                    completion_tokens=agent_run.completion_tokens,
                    total_tokens=agent_run.total_tokens,
                    estimated_cost_usd=agent_run.estimated_cost_usd,
                    latency_ms=agent_run.latency_ms,
                    retry_count=agent_run.retry_count,
                    failure_category=agent_run.failure_category,
                    proposed_patch_id=agent_run.proposed_patch_id,
                    proposed_patch_hash=agent_run.proposed_patch_hash,
                    verification_run_id=agent_run.verification_run_id,
                    plan_approved_by=agent_run.plan_approved_by,
                    plan_approved_at=agent_run.plan_approved_at,
                    issue_analysis_json=agent_run.issue_analysis_json,
                    task_plan_json=agent_run.task_plan_json,
                    patch_proposal_json=agent_run.patch_proposal_json,
                    created_at=agent_run.created_at,
                    completed_at=agent_run.completed_at,
                )
                session.add(record)
            else:
                record.status = agent_run.status.value
                record.attempt_number = agent_run.attempt_number
                record.tool_calls_json = agent_run.tool_calls
                record.prompt_tokens = agent_run.prompt_tokens
                record.completion_tokens = agent_run.completion_tokens
                record.total_tokens = agent_run.total_tokens
                record.estimated_cost_usd = agent_run.estimated_cost_usd
                record.latency_ms = agent_run.latency_ms
                record.retry_count = agent_run.retry_count
                record.failure_category = agent_run.failure_category
                record.proposed_patch_id = agent_run.proposed_patch_id
                record.proposed_patch_hash = agent_run.proposed_patch_hash
                record.verification_run_id = agent_run.verification_run_id
                record.plan_approved_by = agent_run.plan_approved_by
                record.plan_approved_at = agent_run.plan_approved_at
                record.issue_analysis_json = agent_run.issue_analysis_json
                record.task_plan_json = agent_run.task_plan_json
                record.patch_proposal_json = agent_run.patch_proposal_json
                record.completed_at = agent_run.completed_at
        return agent_run

    def get_agent_run(self, run_id: str) -> Optional[AgentRun]:
        """Retrieve an agent run by ID."""
        with self.db.session_scope() as session:
            record = session.get(AgentRunTable, run_id)
            if not record:
                return None
            return self._to_agent_run_model(record)

    def get_agent_runs_for_task(self, task_id: str) -> List[AgentRun]:
        """Retrieve all agent runs for a specific task."""
        with self.db.session_scope() as session:
            stmt = select(AgentRunTable).where(AgentRunTable.task_id == task_id).order_by(AgentRunTable.created_at)
            records = session.scalars(stmt).all()
            return [self._to_agent_run_model(r) for r in records]

    # ---------------- Checkpoints ----------------

    def create_checkpoint(self, chain_id: str) -> Checkpoint:
        """Create a durable checkpoint snapshot of the entire chain state."""
        chain = self.get_chain(chain_id)
        if not chain:
            raise ValueError(f"Task chain '{chain_id}' not found.")

        tasks = self.get_tasks_for_chain(chain_id)
        dependencies = self.get_dependencies_for_chain(chain_id)
        obligations = self.get_obligations_for_chain(chain_id)

        snapshot_data = {
            "chain": chain.model_dump(),
            "tasks": [t.model_dump() for t in tasks],
            "dependencies": [d.model_dump() for d in dependencies],
            "obligations": [o.model_dump() for o in obligations],
        }

        with self.db.session_scope() as session:
            stmt = select(CheckpointTable).where(CheckpointTable.chain_id == chain_id)
            existing_count = len(session.scalars(stmt).all())

            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cp_id = f"chk-{uuid.uuid4().hex[:12]}"
            checkpoint = Checkpoint(
                id=cp_id,
                chain_id=chain_id,
                checkpoint_number=existing_count + 1,
                state_snapshot=snapshot_data,
                created_at=now_utc,
            )

            record = CheckpointTable(
                id=checkpoint.id,
                chain_id=checkpoint.chain_id,
                checkpoint_number=checkpoint.checkpoint_number,
                state_snapshot=checkpoint.state_snapshot,
                created_at=checkpoint.created_at,
            )
            session.add(record)

        return checkpoint

    def get_latest_checkpoint(self, chain_id: str) -> Optional[Checkpoint]:
        """Get the most recent checkpoint for a chain."""
        with self.db.session_scope() as session:
            stmt = (
                select(CheckpointTable)
                .where(CheckpointTable.chain_id == chain_id)
                .order_by(CheckpointTable.checkpoint_number.desc())
            )
            record = session.scalars(stmt).first()
            if not record:
                return None
            return Checkpoint(
                id=record.id,
                chain_id=record.chain_id,
                checkpoint_number=record.checkpoint_number,
                state_snapshot=record.state_snapshot,
                created_at=record.created_at,
            )

    # ---------------- Audit Events ----------------

    def record_audit_event(self, event: AuditEvent) -> AuditEvent:
        """Store an immutable audit event."""
        with self.db.session_scope() as session:
            record = AuditEventTable(
                id=event.id,
                chain_id=event.chain_id,
                task_id=event.task_id,
                actor_type=event.actor_type.value,
                action=event.action,
                metadata_json=event.metadata,
                occurred_at=event.occurred_at,
            )
            session.add(record)
        return event

    def get_audit_events_for_chain(self, chain_id: str) -> List[AuditEvent]:
        """Retrieve audit history for a chain."""
        with self.db.session_scope() as session:
            stmt = (
                select(AuditEventTable)
                .where(AuditEventTable.chain_id == chain_id)
                .order_by(AuditEventTable.occurred_at)
            )
            records = session.scalars(stmt).all()
            return [
                AuditEvent(
                    id=r.id,
                    chain_id=r.chain_id,
                    task_id=r.task_id,
                    actor_type=ActorType(r.actor_type),
                    action=r.action,
                    metadata=r.metadata_json,
                    occurred_at=r.occurred_at,
                )
                for r in records
            ]

    # ---------------- Converters ----------------

    @staticmethod
    def _to_task_model(r: MaintenanceTaskTable) -> MaintenanceTask:
        return MaintenanceTask(
            id=r.id,
            chain_id=r.chain_id,
            title=r.title,
            description=r.description,
            order_index=r.order_index,
            status=TaskStatus(r.status),
            acceptance_criteria=list(r.acceptance_criteria or []),
            candidate_files=list(r.candidate_files or []),
            candidate_symbols=list(r.candidate_symbols or []),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    @staticmethod
    def _to_obligation_model(r: ObligationTable) -> Obligation:
        return Obligation(
            id=r.id,
            chain_id=r.chain_id,
            source_task_id=r.source_task_id,
            description=r.description,
            status=ObligationStatus(r.status),
            verifier_ref=r.verifier_ref,
            status_reason=r.status_reason,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    @staticmethod
    def _to_agent_run_model(r: AgentRunTable) -> AgentRun:
        return AgentRun(
            id=r.id,
            chain_id=r.chain_id,
            task_id=r.task_id,
            provider=r.provider,
            model=r.model,
            status=AgentRunStatus(r.status),
            prompt_hash=r.prompt_hash,
            prompt_version=r.prompt_version,
            attempt_number=r.attempt_number,
            max_repair_attempts=r.max_repair_attempts,
            tool_calls=list(r.tool_calls_json or []),
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.total_tokens,
            estimated_cost_usd=r.estimated_cost_usd,
            latency_ms=r.latency_ms,
            retry_count=r.retry_count,
            failure_category=r.failure_category,
            proposed_patch_id=r.proposed_patch_id,
            proposed_patch_hash=r.proposed_patch_hash,
            verification_run_id=r.verification_run_id,
            plan_approved_by=r.plan_approved_by,
            plan_approved_at=r.plan_approved_at,
            issue_analysis_json=r.issue_analysis_json,
            task_plan_json=r.task_plan_json,
            patch_proposal_json=r.patch_proposal_json,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )

    # ---------------- Webhook Deliveries ----------------

    def save_webhook_delivery(
        self,
        delivery_id: str,
        event_type: str,
        payload_hash: str,
        action: Optional[str] = None,
        status: str = "processed",
    ) -> bool:
        """Record a processed webhook delivery ID for idempotency."""
        with self.db.session_scope() as session:
            existing = session.scalar(
                select(GitHubWebhookDeliveryTable).where(GitHubWebhookDeliveryTable.delivery_id == delivery_id)
            )
            if existing:
                return False
            now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            row = GitHubWebhookDeliveryTable(
                id=f"dlv-{uuid.uuid4().hex[:12]}",
                delivery_id=delivery_id,
                event_type=event_type,
                action=action,
                payload_hash=payload_hash,
                processed_at=now_utc,
                status=status,
            )
            session.add(row)
            return True

    def is_delivery_processed(self, delivery_id: str) -> bool:
        """Check if a webhook delivery has already been processed."""
        with self.db.session_scope() as session:
            existing = session.scalar(
                select(GitHubWebhookDeliveryTable).where(GitHubWebhookDeliveryTable.delivery_id == delivery_id)
            )
            return existing is not None

    # ---------------- Dashboard & Cross-Chain Queries ----------------

    def list_all_tasks(self, limit: int = 100, offset: int = 0) -> List[MaintenanceTask]:
        """List all maintenance tasks across all chains."""
        with self.db.session_scope() as session:
            stmt = select(MaintenanceTaskTable).order_by(MaintenanceTaskTable.order_index).offset(offset).limit(limit)
            rows = session.scalars(stmt).all()
            return [self._to_task_model(r) for r in rows]

    def list_all_obligations(self, limit: int = 100, offset: int = 0) -> List[Obligation]:
        """List all obligations across all chains."""
        with self.db.session_scope() as session:
            stmt = select(ObligationTable).order_by(ObligationTable.created_at.desc()).offset(offset).limit(limit)
            rows = session.scalars(stmt).all()
            return [self._to_obligation_model(r) for r in rows]

    def list_all_agent_runs(self, limit: int = 50, offset: int = 0) -> List[AgentRun]:
        """List recent agent runs across all tasks."""
        with self.db.session_scope() as session:
            stmt = select(AgentRunTable).order_by(AgentRunTable.created_at.desc()).offset(offset).limit(limit)
            rows = session.scalars(stmt).all()
            return [self._to_agent_run_model(r) for r in rows]

    def list_all_verification_runs(self, limit: int = 50, offset: int = 0) -> List[VerificationRun]:
        """List recent verification runs across all patches."""
        with self.db.session_scope() as session:
            stmt = select(VerificationRunTable).order_by(VerificationRunTable.started_at.desc()).offset(offset).limit(limit)
            rows = session.scalars(stmt).all()
            results = []
            for record in rows:
                checks = [VerificationCheck.model_validate(c) for c in (record.checks_json or [])]
                rechecks = [ObligationRecheckResult.model_validate(o) for o in (record.obligation_rechecks_json or [])]
                results.append(
                    VerificationRun(
                        id=record.id,
                        patch_id=record.patch_id,
                        task_id=record.task_id,
                        chain_id=record.chain_id,
                        base_sha=record.base_sha,
                        workspace_id=record.workspace_id,
                        sandbox_type=SandboxType(record.sandbox_type),
                        image_tag=record.image_tag,
                        image_digest=record.image_digest,
                        started_at=record.started_at,
                        completed_at=record.completed_at,
                        status=VerificationRunStatus(record.status),
                        checks=checks,
                        obligation_rechecks=rechecks,
                        has_regressions=record.has_regressions,
                    )
                )
            return results

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Compute summary metrics across all persisted entities."""
        with self.db.session_scope() as session:
            chains = session.scalars(select(TaskChainTable)).all()
            tasks = session.scalars(select(MaintenanceTaskTable)).all()
            obligations = session.scalars(select(ObligationTable)).all()
            agent_runs = session.scalars(select(AgentRunTable).order_by(AgentRunTable.created_at.desc()).limit(5)).all()
            v_runs = session.scalars(select(VerificationRunTable).order_by(VerificationRunTable.started_at.desc()).limit(5)).all()

            # Task status counts
            task_status_counts: Dict[str, int] = {}
            for t in tasks:
                task_status_counts[t.status] = task_status_counts.get(t.status, 0) + 1

            # Obligation status counts
            active_obs = [o for o in obligations if o.status == ObligationStatus.ACTIVE.value]
            superseded_obs = [o for o in obligations if o.status == ObligationStatus.SUPERSEDED.value]
            withdrawn_obs = [o for o in obligations if o.status == ObligationStatus.WITHDRAWN.value]

            # Repositories
            repo_ids = sorted(list(set(c.repository_id for c in chains)))

            # Regression warnings
            regression_count = sum(1 for v in v_runs if v.has_regressions)

            return {
                "total_chains": len(chains),
                "total_tasks": len(tasks),
                "task_status_counts": task_status_counts,
                "total_obligations": len(obligations),
                "active_obligations": len(active_obs),
                "superseded_obligations": len(superseded_obs),
                "withdrawn_obligations": len(withdrawn_obs),
                "recent_agent_runs_count": len(agent_runs),
                "recent_verification_runs_count": len(v_runs),
                "regressions_detected_recent": regression_count,
                "registered_repositories": repo_ids,
            }

    # ---------------- Publication Approvals & Runs ----------------

    def save_publication_approval(self, approval: PublicationApproval) -> PublicationApproval:
        """Create or update a publication approval record."""
        with self.db.session_scope() as session:
            existing = session.get(PublicationApprovalTable, approval.id)
            if existing:
                existing.status = approval.status.value
                existing.approver_identity = approval.approver_identity
                existing.approved_at = approval.approved_at
                existing.expires_at = approval.expires_at
                existing.invalidation_reason = approval.invalidation_reason
                existing.approval_metadata = approval.metadata
            else:
                record = PublicationApprovalTable(
                    id=approval.id,
                    repository_owner=approval.repository_owner,
                    repository_name=approval.repository_name,
                    repository_id=approval.repository_id,
                    task_id=approval.task_id,
                    chain_id=approval.chain_id,
                    patch_id=approval.patch_id,
                    patch_hash=approval.patch_hash,
                    base_commit_sha=approval.base_commit_sha,
                    target_base_branch=approval.target_base_branch,
                    proposed_head_branch=approval.proposed_head_branch,
                    verification_report_id=approval.verification_report_id,
                    verification_run_id=approval.verification_run_id,
                    approver_identity=approval.approver_identity,
                    status=approval.status.value,
                    invalidation_reason=approval.invalidation_reason,
                    created_at=approval.created_at,
                    approved_at=approval.approved_at,
                    expires_at=approval.expires_at,
                    approval_metadata=approval.metadata,
                )
                session.add(record)
        return approval

    def get_publication_approval(self, approval_id: str) -> Optional[PublicationApproval]:
        """Retrieve a publication approval record by ID."""
        with self.db.session_scope() as session:
            record = session.get(PublicationApprovalTable, approval_id)
            if not record:
                return None
            return self._to_approval_model(record)

    def list_publication_approvals(self, task_id: Optional[str] = None) -> List[PublicationApproval]:
        """List publication approval records, optionally filtered by task."""
        with self.db.session_scope() as session:
            stmt = select(PublicationApprovalTable)
            if task_id:
                stmt = stmt.where(PublicationApprovalTable.task_id == task_id)
            stmt = stmt.order_by(PublicationApprovalTable.created_at.desc())
            records = session.scalars(stmt).all()
            return [self._to_approval_model(r) for r in records]

    def _to_approval_model(self, record: PublicationApprovalTable) -> PublicationApproval:
        return PublicationApproval(
            id=record.id,
            repository_owner=record.repository_owner,
            repository_name=record.repository_name,
            repository_id=record.repository_id,
            task_id=record.task_id,
            chain_id=record.chain_id,
            patch_id=record.patch_id,
            patch_hash=record.patch_hash,
            base_commit_sha=record.base_commit_sha,
            target_base_branch=record.target_base_branch,
            proposed_head_branch=record.proposed_head_branch,
            verification_report_id=record.verification_report_id,
            verification_run_id=record.verification_run_id,
            approver_identity=record.approver_identity,
            status=ApprovalStatus(record.status),
            invalidation_reason=record.invalidation_reason,
            created_at=record.created_at,
            approved_at=record.approved_at,
            expires_at=record.expires_at,
            metadata=record.approval_metadata or {},
        )

    def save_publication_run(self, run: PublicationRun) -> PublicationRun:
        """Create or update a publication execution record."""
        with self.db.session_scope() as session:
            existing = session.get(PublicationRunTable, run.id)
            if existing:
                existing.status = run.status.value
                existing.head_commit_sha = run.head_commit_sha
                existing.pull_request_number = run.pull_request_number
                existing.pull_request_url = run.pull_request_url
                existing.attempt_count = run.attempt_count
                existing.error_message = run.error_message
                existing.completed_at = run.completed_at
            else:
                record = PublicationRunTable(
                    id=run.id,
                    approval_id=run.approval_id,
                    task_id=run.task_id,
                    chain_id=run.chain_id,
                    repository_owner=run.repository_owner,
                    repository_name=run.repository_name,
                    head_branch=run.head_branch,
                    base_branch=run.base_branch,
                    base_commit_sha=run.base_commit_sha,
                    head_commit_sha=run.head_commit_sha,
                    pull_request_number=run.pull_request_number,
                    pull_request_url=run.pull_request_url,
                    status=run.status.value,
                    attempt_count=run.attempt_count,
                    error_message=run.error_message,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                )
                session.add(record)
        return run

    def get_publication_run(self, run_id: str) -> Optional[PublicationRun]:
        """Retrieve a publication run by ID."""
        with self.db.session_scope() as session:
            record = session.get(PublicationRunTable, run_id)
            if not record:
                return None
            return self._to_publication_run_model(record)

    def list_publication_runs(self, approval_id: Optional[str] = None) -> List[PublicationRun]:
        """List publication runs ordered by started_at."""
        with self.db.session_scope() as session:
            stmt = select(PublicationRunTable)
            if approval_id:
                stmt = stmt.where(PublicationRunTable.approval_id == approval_id)
            stmt = stmt.order_by(PublicationRunTable.started_at.desc())
            records = session.scalars(stmt).all()
            return [self._to_publication_run_model(r) for r in records]

    def _to_publication_run_model(self, record: PublicationRunTable) -> PublicationRun:
        return PublicationRun(
            id=record.id,
            approval_id=record.approval_id,
            task_id=record.task_id,
            chain_id=record.chain_id,
            repository_owner=record.repository_owner,
            repository_name=record.repository_name,
            head_branch=record.head_branch,
            base_branch=record.base_branch,
            base_commit_sha=record.base_commit_sha,
            head_commit_sha=record.head_commit_sha,
            pull_request_number=record.pull_request_number,
            pull_request_url=record.pull_request_url,
            status=ApprovalStatus(record.status),
            attempt_count=record.attempt_count,
            error_message=record.error_message,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )

    def save_published_pull_request(self, pr: PublishedPullRequest) -> PublishedPullRequest:
        """Store a published pull request record."""
        with self.db.session_scope() as session:
            existing = session.get(PublishedPullRequestTable, pr.id)
            if not existing:
                record = PublishedPullRequestTable(
                    id=pr.id,
                    run_id=pr.run_id,
                    approval_id=pr.approval_id,
                    repository_owner=pr.repository_owner,
                    repository_name=pr.repository_name,
                    pr_number=pr.pr_number,
                    html_url=pr.html_url,
                    title=pr.title,
                    body=pr.body,
                    head_branch=pr.head_branch,
                    base_branch=pr.base_branch,
                    head_sha=pr.head_sha,
                    base_sha=pr.base_sha,
                    created_at=pr.created_at,
                )
                session.add(record)
        return pr

    def get_published_pull_request(self, pr_id: str) -> Optional[PublishedPullRequest]:
        """Retrieve a published pull request record."""
        with self.db.session_scope() as session:
            record = session.get(PublishedPullRequestTable, pr_id)
            if not record:
                return None
            return self._to_published_pr_model(record)

    def list_published_pull_requests(self) -> List[PublishedPullRequest]:
        """List all published pull requests ordered by creation time."""
        with self.db.session_scope() as session:
            stmt = select(PublishedPullRequestTable).order_by(PublishedPullRequestTable.created_at.desc())
            records = session.scalars(stmt).all()
            return [self._to_published_pr_model(r) for r in records]

    def _to_published_pr_model(self, record: PublishedPullRequestTable) -> PublishedPullRequest:
        return PublishedPullRequest(
            id=record.id,
            run_id=record.run_id,
            approval_id=record.approval_id,
            repository_owner=record.repository_owner,
            repository_name=record.repository_name,
            pr_number=record.pr_number,
            html_url=record.html_url,
            title=record.title,
            body=record.body,
            head_branch=record.head_branch,
            base_branch=record.base_branch,
            head_sha=record.head_sha,
            base_sha=record.base_sha,
            created_at=record.created_at,
        )

    # ---------------- Benchmark Runs ----------------

    def save_benchmark_run(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store benchmark experiment results."""
        with self.db.session_scope() as session:
            existing = session.get(BenchmarkRunTable, run_data["id"])
            if existing:
                existing.completed_chains = run_data.get("completed_chains", existing.completed_chains)
                existing.successful_tasks = run_data.get("successful_tasks", existing.successful_tasks)
                existing.regressions_count = run_data.get("regressions_count", existing.regressions_count)
                existing.metrics = run_data.get("metrics", existing.metrics)
            else:
                record = BenchmarkRunTable(
                    id=run_data["id"],
                    baseline=run_data["baseline"],
                    corpus_id=run_data.get("corpus_id", "controlled_corpus_v1"),
                    total_chains=run_data.get("total_chains", 0),
                    completed_chains=run_data.get("completed_chains", 0),
                    total_tasks=run_data.get("total_tasks", 0),
                    successful_tasks=run_data.get("successful_tasks", 0),
                    regressions_count=run_data.get("regressions_count", 0),
                    metrics=run_data.get("metrics", {}),
                    raw_results_path=run_data.get("raw_results_path"),
                    executed_at=run_data.get("executed_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                )
                session.add(record)
        return run_data

    def get_benchmark_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve benchmark run by ID."""
        with self.db.session_scope() as session:
            record = session.get(BenchmarkRunTable, run_id)
            if not record:
                return None
            return {
                "id": record.id,
                "baseline": record.baseline,
                "corpus_id": record.corpus_id,
                "total_chains": record.total_chains,
                "completed_chains": record.completed_chains,
                "total_tasks": record.total_tasks,
                "successful_tasks": record.successful_tasks,
                "regressions_count": record.regressions_count,
                "metrics": record.metrics,
                "raw_results_path": record.raw_results_path,
                "executed_at": record.executed_at,
            }

    def list_benchmark_runs(self) -> List[Dict[str, Any]]:
        """List all benchmark runs ordered by executed_at."""
        with self.db.session_scope() as session:
            stmt = select(BenchmarkRunTable).order_by(BenchmarkRunTable.executed_at.desc())
            records = session.scalars(stmt).all()
            return [
                {
                    "id": r.id,
                    "baseline": r.baseline,
                    "corpus_id": r.corpus_id,
                    "total_chains": r.total_chains,
                    "completed_chains": r.completed_chains,
                    "total_tasks": r.total_tasks,
                    "successful_tasks": r.successful_tasks,
                    "regressions_count": r.regressions_count,
                    "metrics": r.metrics,
                    "raw_results_path": r.raw_results_path,
                    "executed_at": r.executed_at,
                }
                for r in records
            ]
