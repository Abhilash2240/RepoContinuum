"""Repository pattern implementation for durable persistence of task chains."""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.tables import (
    AuditEventTable,
    CheckpointTable,
    MaintenanceTaskTable,
    ObligationTable,
    TaskChainTable,
    TaskDependencyTable,
)


class TaskChainRepository:
    """Provides atomic query and mutation methods for the task chain domain."""

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
            # Count existing checkpoints to increment checkpoint_number
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

    def list_checkpoints(self, chain_id: str) -> List[Checkpoint]:
        """List all checkpoints for a chain in chronological order."""
        with self.db.session_scope() as session:
            stmt = (
                select(CheckpointTable)
                .where(CheckpointTable.chain_id == chain_id)
                .order_by(CheckpointTable.checkpoint_number)
            )
            records = session.scalars(stmt).all()
            return [
                Checkpoint(
                    id=r.id,
                    chain_id=r.chain_id,
                    checkpoint_number=r.checkpoint_number,
                    state_snapshot=r.state_snapshot,
                    created_at=r.created_at,
                )
                for r in records
            ]

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
