"""Application domain service orchestrating task chains, obligations, and transitions."""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from repocontinuum.domain.planning import (
    ActorType,
    AuditEvent,
    ChainStatus,
    Checkpoint,
    DAGValidationReport,
    DependencySource,
    MaintenanceTask,
    Obligation,
    ObligationStatus,
    TaskChain,
    TaskDependency,
    TaskStatus,
)
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.dag import CycleDetectedError, DependencyGraph
from repocontinuum.planning.obligation_ledger import ObligationLedger
from repocontinuum.planning.state_machine import TaskStateMachine


class TaskChainService:
    """Core domain service for managing task chains, DAG validation, and obligation ledgers."""

    def __init__(self, repository: TaskChainRepository):
        self.repo = repository

    # ---------------- Task Chain Operations ----------------

    def create_chain(
        self,
        title: str,
        repository_id: str,
        description: str = "",
        actor: ActorType = ActorType.USER,
    ) -> TaskChain:
        """Create and persist a new maintenance task chain."""
        if not title.strip():
            raise ValueError("Task chain title cannot be empty.")

        chain_id = f"chn-{uuid.uuid4().hex[:12]}"
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        chain = TaskChain(
            id=chain_id,
            repository_id=repository_id,
            title=title.strip(),
            description=description.strip(),
            status=ChainStatus.CREATED,
            created_at=now_utc,
            updated_at=now_utc,
        )
        self.repo.save_chain(chain)

        self._record_audit(
            chain_id=chain.id,
            task_id=None,
            actor_type=actor,
            action="CREATE_CHAIN",
            metadata={"title": chain.title, "repository_id": repository_id},
        )
        return chain

    def get_chain(self, chain_id: str) -> Optional[TaskChain]:
        """Retrieve a task chain by ID."""
        return self.repo.get_chain(chain_id)

    def list_chains(self) -> List[TaskChain]:
        """List all registered task chains."""
        return self.repo.list_chains()

    # ---------------- Task Operations ----------------

    def add_task(
        self,
        chain_id: str,
        title: str,
        description: str = "",
        acceptance_criteria: Optional[List[str]] = None,
        candidate_files: Optional[List[str]] = None,
        candidate_symbols: Optional[List[str]] = None,
        order_index: int = 0,
        actor: ActorType = ActorType.USER,
    ) -> MaintenanceTask:
        """Add a maintenance task to a chain, creating active obligations for declared acceptance criteria."""
        chain = self.repo.get_chain(chain_id)
        if not chain:
            raise ValueError(f"Task chain '{chain_id}' does not exist.")

        if not title.strip():
            raise ValueError("Task title cannot be empty.")

        task_id = f"tsk-{uuid.uuid4().hex[:12]}"
        criteria = acceptance_criteria or []
        files = candidate_files or []
        symbols = candidate_symbols or []

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        task = MaintenanceTask(
            id=task_id,
            chain_id=chain_id,
            title=title.strip(),
            description=description.strip(),
            order_index=order_index,
            status=TaskStatus.CREATED,
            acceptance_criteria=criteria,
            candidate_files=files,
            candidate_symbols=symbols,
            created_at=now_utc,
            updated_at=now_utc,
        )
        self.repo.save_task(task)

        # Create corresponding initial active obligations for declared criteria
        for idx, criterion in enumerate(criteria, start=1):
            ob_id = f"ob-{uuid.uuid4().hex[:12]}"
            obligation = ObligationLedger.create_obligation(
                id=ob_id,
                chain_id=chain_id,
                source_task_id=task.id,
                description=criterion,
                verifier_ref=f"{task.id}:criterion_{idx}",
            )
            self.repo.save_obligation(obligation)

        # Evaluate and set task readiness (READY or BLOCKED)
        self._refresh_task_readiness(chain_id)
        refreshed_task = self.repo.get_task(task.id) or task

        self._record_audit(
            chain_id=chain_id,
            task_id=task.id,
            actor_type=actor,
            action="ADD_TASK",
            metadata={"title": task.title, "acceptance_criteria_count": len(criteria)},
        )
        return refreshed_task

    # ---------------- Dependency Operations ----------------

    def add_dependency(
        self,
        chain_id: str,
        predecessor_task_id: str,
        successor_task_id: str,
        source: DependencySource = DependencySource.USER_DECLARED,
        approved_by: Optional[str] = None,
        actor: ActorType = ActorType.USER,
    ) -> TaskDependency:
        """Establish a directed dependency edge and validate that it does not form a cycle."""
        if predecessor_task_id == successor_task_id:
            raise CycleDetectedError([predecessor_task_id, successor_task_id])

        # Validate tasks exist in the chain
        tasks = self.repo.get_tasks_for_chain(chain_id)
        task_ids = {t.id for t in tasks}
        if predecessor_task_id not in task_ids:
            raise ValueError(f"Predecessor task '{predecessor_task_id}' not found in chain '{chain_id}'.")
        if successor_task_id not in task_ids:
            raise ValueError(f"Successor task '{successor_task_id}' not found in chain '{chain_id}'.")

        existing_deps = self.repo.get_dependencies_for_chain(chain_id)

        # Check for duplicate
        for d in existing_deps:
            if d.predecessor_task_id == predecessor_task_id and d.successor_task_id == successor_task_id:
                return d

        # Construct candidate dependency
        dep_id = f"dep-{uuid.uuid4().hex[:12]}"
        candidate_dep = TaskDependency(
            id=dep_id,
            chain_id=chain_id,
            predecessor_task_id=predecessor_task_id,
            successor_task_id=successor_task_id,
            source=source,
            approved_by=approved_by,
        )

        # Pre-validate cycle with prospective edge
        test_graph = DependencyGraph(tasks, existing_deps + [candidate_dep])
        report = test_graph.validate(chain_id)
        if report.has_cycles:
            raise CycleDetectedError(report.cycle_paths[0])

        self.repo.add_dependency(candidate_dep)

        # Re-evaluate tasks to mark blocked tasks
        self._refresh_task_readiness(chain_id)

        self._record_audit(
            chain_id=chain_id,
            task_id=successor_task_id,
            actor_type=actor,
            action="ADD_DEPENDENCY",
            metadata={
                "predecessor": predecessor_task_id,
                "successor": successor_task_id,
            },
        )
        return candidate_dep

    # ---------------- Validation & Planning ----------------

    def validate_chain(self, chain_id: str) -> DAGValidationReport:
        """Validate entire chain DAG, detect cycles, and identify blocked tasks."""
        tasks = self.repo.get_tasks_for_chain(chain_id)
        dependencies = self.repo.get_dependencies_for_chain(chain_id)
        graph = DependencyGraph(tasks, dependencies)
        report = graph.validate(chain_id)

        # Update blocked/ready statuses accordingly
        if report.is_valid:
            self._refresh_task_readiness(chain_id)

        return report

    def get_execution_plan(self, chain_id: str) -> List[MaintenanceTask]:
        """Return tasks sorted in stable topological execution order."""
        report = self.validate_chain(chain_id)
        if not report.is_valid:
            raise ValueError(f"Cannot generate plan for invalid chain: {report.explanation}")

        tasks_by_id = {t.id: t for t in self.repo.get_tasks_for_chain(chain_id)}
        return [tasks_by_id[task_id] for task_id in report.topological_order if task_id in tasks_by_id]

    # ---------------- Lifecycle State Transitions ----------------

    def start_task(
        self,
        task_id: str,
        waive_dependencies: bool = False,
        actor: ActorType = ActorType.USER,
    ) -> MaintenanceTask:
        """Transition task to IN_PROGRESS after enforcing prerequisite dependency gates."""
        task = self.repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        tasks = self.repo.get_tasks_for_chain(task.chain_id)
        dependencies = self.repo.get_dependencies_for_chain(task.chain_id)
        graph = DependencyGraph(tasks, dependencies)
        is_blocked, unmet = graph.is_task_blocked(task.id)

        TaskStateMachine.validate_transition(
            task_id=task.id,
            current_status=task.status,
            target_status=TaskStatus.IN_PROGRESS,
            unmet_dependencies=unmet,
            explicit_waiver=waive_dependencies,
        )

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_task = task.model_copy(
            update={
                "status": TaskStatus.IN_PROGRESS,
                "updated_at": now_utc,
            }
        )
        self.repo.save_task(updated_task)

        self._record_audit(
            chain_id=task.chain_id,
            task_id=task.id,
            actor_type=actor,
            action="START_TASK",
            metadata={"waived": waive_dependencies, "unmet": unmet},
        )
        return updated_task

    def complete_task(
        self,
        task_id: str,
        actor: ActorType = ActorType.USER,
    ) -> MaintenanceTask:
        """Mark task COMPLETED and unblock eligible dependent tasks."""
        task = self.repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        TaskStateMachine.validate_transition(
            task_id=task.id,
            current_status=task.status,
            target_status=TaskStatus.COMPLETED,
            unmet_dependencies=[],
        )

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_task = task.model_copy(
            update={
                "status": TaskStatus.COMPLETED,
                "updated_at": now_utc,
            }
        )
        self.repo.save_task(updated_task)

        # Refresh dependent tasks in the chain
        self._refresh_task_readiness(task.chain_id)

        self._record_audit(
            chain_id=task.chain_id,
            task_id=task.id,
            actor_type=actor,
            action="COMPLETE_TASK",
            metadata={},
        )
        return updated_task

    def fail_task(
        self,
        task_id: str,
        reason: str,
        actor: ActorType = ActorType.USER,
    ) -> MaintenanceTask:
        """Mark task FAILED while strictly preserving all active obligations intact."""
        task = self.repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        TaskStateMachine.validate_transition(
            task_id=task.id,
            current_status=task.status,
            target_status=TaskStatus.FAILED,
            unmet_dependencies=[],
        )

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updated_task = task.model_copy(
            update={
                "status": TaskStatus.FAILED,
                "updated_at": now_utc,
            }
        )
        self.repo.save_task(updated_task)

        # Re-check chain readiness (successors become blocked)
        self._refresh_task_readiness(task.chain_id)

        # CRITICAL: Active obligations remain active! Never deleted or withdrawn automatically.
        self._record_audit(
            chain_id=task.chain_id,
            task_id=task.id,
            actor_type=actor,
            action="FAIL_TASK",
            metadata={"failure_reason": reason},
        )
        return updated_task

    # ---------------- Obligation Ledger Operations ----------------

    def supersede_obligation(
        self,
        obligation_id: str,
        reason: str,
        new_verifier_ref: Optional[str] = None,
        actor: ActorType = ActorType.USER,
    ) -> Obligation:
        """Supersede an existing obligation with an explicit recorded justification."""
        ob = self.repo.get_obligation(obligation_id)
        if not ob:
            raise ValueError(f"Obligation '{obligation_id}' not found.")

        superseded = ObligationLedger.supersede_obligation(ob, reason, new_verifier_ref)
        self.repo.save_obligation(superseded)

        self._record_audit(
            chain_id=ob.chain_id,
            task_id=ob.source_task_id,
            actor_type=actor,
            action="SUPERSEDE_OBLIGATION",
            metadata={"obligation_id": ob.id, "reason": reason},
        )
        return superseded

    def withdraw_obligation(
        self,
        obligation_id: str,
        reason: str,
        actor: ActorType = ActorType.USER,
    ) -> Obligation:
        """Withdraw an obsolete obligation with an explicit recorded justification."""
        ob = self.repo.get_obligation(obligation_id)
        if not ob:
            raise ValueError(f"Obligation '{obligation_id}' not found.")

        withdrawn = ObligationLedger.withdraw_obligation(ob, reason)
        self.repo.save_obligation(withdrawn)

        self._record_audit(
            chain_id=ob.chain_id,
            task_id=ob.source_task_id,
            actor_type=actor,
            action="WITHDRAW_OBLIGATION",
            metadata={"obligation_id": ob.id, "reason": reason},
        )
        return withdrawn

    def get_obligations_for_chain(self, chain_id: str) -> List[Obligation]:
        """Retrieve all obligations for a chain."""
        return self.repo.get_obligations_for_chain(chain_id)

    # ---------------- Checkpoints & Resumption ----------------

    def create_checkpoint(
        self,
        chain_id: str,
        actor: ActorType = ActorType.USER,
    ) -> Checkpoint:
        """Create a persistent checkpoint snapshot for process pause and resume."""
        checkpoint = self.repo.create_checkpoint(chain_id)
        self._record_audit(
            chain_id=chain_id,
            task_id=None,
            actor_type=actor,
            action="CREATE_CHECKPOINT",
            metadata={"checkpoint_number": checkpoint.checkpoint_number, "checkpoint_id": checkpoint.id},
        )
        return checkpoint

    def get_latest_checkpoint(self, chain_id: str) -> Optional[Checkpoint]:
        """Retrieve the latest checkpoint for a chain."""
        return self.repo.get_latest_checkpoint(chain_id)

    def resume_chain(
        self,
        chain_id: str,
        actor: ActorType = ActorType.USER,
    ) -> TaskChain:
        """Resume a chain from its latest checkpoint or current database state."""
        chain = self.repo.get_chain(chain_id)
        if not chain:
            raise ValueError(f"Task chain '{chain_id}' not found.")

        # Re-validate chain and refresh readiness
        self._refresh_task_readiness(chain_id)

        self._record_audit(
            chain_id=chain_id,
            task_id=None,
            actor_type=actor,
            action="RESUME_CHAIN",
            metadata={"status": chain.status.value},
        )
        return chain

    # ---------------- Helper Methods ----------------

    def _refresh_task_readiness(self, chain_id: str) -> None:
        """Update tasks to BLOCKED or READY based on predecessor statuses."""
        tasks = self.repo.get_tasks_for_chain(chain_id)
        dependencies = self.repo.get_dependencies_for_chain(chain_id)
        graph = DependencyGraph(tasks, dependencies)

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for t in tasks:
            if t.status in {
                TaskStatus.IN_PROGRESS,
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                continue

            is_blocked, unmet = graph.is_task_blocked(t.id)
            new_status = TaskStatus.BLOCKED if is_blocked else TaskStatus.READY

            if t.status != new_status:
                updated_task = t.model_copy(
                    update={
                        "status": new_status,
                        "updated_at": now_utc,
                    }
                )
                self.repo.save_task(updated_task)

    def _record_audit(
        self,
        chain_id: str,
        task_id: Optional[str],
        actor_type: ActorType,
        action: str,
        metadata: dict,
    ) -> None:
        """Helper to create and persist audit events."""
        event = AuditEvent(
            id=f"aud-{uuid.uuid4().hex[:12]}",
            chain_id=chain_id,
            task_id=task_id,
            actor_type=actor_type,
            action=action,
            metadata=metadata,
        )
        self.repo.record_audit_event(event)
