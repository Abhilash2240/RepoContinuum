"""SQLAlchemy ORM tables for task chains, dependencies, obligations, checkpoints, and audits."""

from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy import (
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from repocontinuum.persistence.database import Base


class TaskChainTable(Base):
    """Database representation of a maintenance task chain."""
    __tablename__ = "task_chains"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    tasks: Mapped[List[MaintenanceTaskTable]] = relationship(
        "MaintenanceTaskTable",
        back_populates="chain",
        cascade="all, delete-orphan",
        order_by="MaintenanceTaskTable.order_index",
    )
    dependencies: Mapped[List[TaskDependencyTable]] = relationship(
        "TaskDependencyTable",
        back_populates="chain",
        cascade="all, delete-orphan",
    )
    obligations: Mapped[List[ObligationTable]] = relationship(
        "ObligationTable",
        back_populates="chain",
        cascade="all, delete-orphan",
    )
    checkpoints: Mapped[List[CheckpointTable]] = relationship(
        "CheckpointTable",
        back_populates="chain",
        cascade="all, delete-orphan",
        order_by="CheckpointTable.checkpoint_number",
    )
    audit_events: Mapped[List[AuditEventTable]] = relationship(
        "AuditEventTable",
        back_populates="chain",
        cascade="all, delete-orphan",
        order_by="AuditEventTable.occurred_at",
    )


class MaintenanceTaskTable(Base):
    """Database representation of an individual maintenance task."""
    __tablename__ = "maintenance_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain_id: Mapped[str] = mapped_column(String(64), ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    acceptance_criteria: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    candidate_files: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    candidate_symbols: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    chain: Mapped[TaskChainTable] = relationship("TaskChainTable", back_populates="tasks")


class TaskDependencyTable(Base):
    """Directed dependency link between two tasks."""
    __tablename__ = "task_dependencies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain_id: Mapped[str] = mapped_column(String(64), ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False)
    predecessor_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    successor_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)

    chain: Mapped[TaskChainTable] = relationship("TaskChainTable", back_populates="dependencies")

    __table_args__ = (
        UniqueConstraint("chain_id", "predecessor_task_id", "successor_task_id", name="uq_task_dependency"),
    )


class ObligationTable(Base):
    """Database representation of an active, superseded, or withdrawn acceptance obligation."""
    __tablename__ = "obligations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain_id: Mapped[str] = mapped_column(String(64), ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False)
    source_task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    verifier_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    chain: Mapped[TaskChainTable] = relationship("TaskChainTable", back_populates="obligations")


class CheckpointTable(Base):
    """Immutable state snapshot for pausing and resuming a chain."""
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain_id: Mapped[str] = mapped_column(String(64), ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False)
    checkpoint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)

    chain: Mapped[TaskChainTable] = relationship("TaskChainTable", back_populates="checkpoints")


class AuditEventTable(Base):
    """Audit event tracking actions and decisions."""
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain_id: Mapped[str] = mapped_column(String(64), ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String(64), nullable=False)

    chain: Mapped[TaskChainTable] = relationship("TaskChainTable", back_populates="audit_events")
