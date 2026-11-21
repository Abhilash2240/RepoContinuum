"""Domain data models and schemas for task chains, dependencies, and obligations."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """Lifecycle states of a maintenance task."""
    CREATED = "CREATED"
    READY = "READY"
    PLANNED = "PLANNED"
    BLOCKED = "BLOCKED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ChainStatus(str, Enum):
    """Lifecycle states of a maintenance task chain."""
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ObligationStatus(str, Enum):
    """Lifecycle states of an acceptance obligation."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class DependencySource(str, Enum):
    """Origin of a task dependency."""
    USER_DECLARED = "user_declared"
    INFERRED = "inferred"
    MODEL_SUGGESTED = "model_suggested"


class ActorType(str, Enum):
    """Actor executing an action in the system."""
    USER = "user"
    SYSTEM = "system"
    MODEL = "model"


class TaskDependency(BaseModel):
    """Explicit directed predecessor -> successor dependency between tasks."""
    model_config = ConfigDict(frozen=True)

    id: str
    chain_id: str
    predecessor_task_id: str
    successor_task_id: str
    source: DependencySource = DependencySource.USER_DECLARED
    approved_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class Obligation(BaseModel):
    """Active or historical acceptance requirement tied to a task and verifier."""
    model_config = ConfigDict(frozen=True)

    id: str
    chain_id: str
    source_task_id: str
    description: str
    status: ObligationStatus = ObligationStatus.ACTIVE
    verifier_ref: Optional[str] = None
    status_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class MaintenanceTask(BaseModel):
    """Individual unit of maintenance work within a chain."""
    model_config = ConfigDict(frozen=True)

    id: str
    chain_id: str
    title: str
    description: str = ""
    order_index: int = 0
    status: TaskStatus = TaskStatus.CREATED
    acceptance_criteria: List[str] = Field(default_factory=list)
    candidate_files: List[str] = Field(default_factory=list)
    candidate_symbols: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class TaskChain(BaseModel):
    """A sequence or DAG of dependent maintenance tasks."""
    model_config = ConfigDict(frozen=True)

    id: str
    repository_id: str
    title: str
    description: str = ""
    status: ChainStatus = ChainStatus.CREATED
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class Checkpoint(BaseModel):
    """Durable state snapshot enabling pause and resume of a task chain."""
    model_config = ConfigDict(frozen=True)

    id: str
    chain_id: str
    checkpoint_number: int
    state_snapshot: Dict[str, Any]
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class AuditEvent(BaseModel):
    """Immutable audit trail event recording actions and decisions."""
    model_config = ConfigDict(frozen=True)

    id: str
    chain_id: str
    task_id: Optional[str] = None
    actor_type: ActorType
    action: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class DAGValidationReport(BaseModel):
    """Validation report and execution plan for a task chain."""
    model_config = ConfigDict(frozen=True)

    chain_id: str
    is_valid: bool
    has_cycles: bool
    cycle_paths: List[List[str]] = Field(default_factory=list)
    missing_dependencies: List[str] = Field(default_factory=list)
    topological_order: List[str] = Field(default_factory=list)
    blocked_tasks: Dict[str, List[str]] = Field(default_factory=dict)
    explanation: str
