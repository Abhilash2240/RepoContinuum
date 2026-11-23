"""SQLAlchemy ORM tables for task chains, dependencies, obligations, checkpoints, patches, and verification."""

from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy import (
    Boolean,
    Float,
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
    patches: Mapped[List[PatchTable]] = relationship("PatchTable", back_populates="task", cascade="all, delete-orphan")


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


class PatchTable(Base):
    """Durable record of a validated patch bound to a base commit SHA and hash."""
    __tablename__ = "patches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    diff_content: Mapped[str] = mapped_column(Text, nullable=False)
    changed_paths: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    total_added_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_removed_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)

    task: Mapped[MaintenanceTaskTable] = relationship("MaintenanceTaskTable", back_populates="patches")
    verification_runs: Mapped[List[VerificationRunTable]] = relationship("VerificationRunTable", back_populates="patch", cascade="all, delete-orphan")


class VerificationRunTable(Base):
    """Durable record of an isolated verification execution run."""
    __tablename__ = "verification_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patch_id: Mapped[str] = mapped_column(String(64), ForeignKey("patches.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chain_id: Mapped[str] = mapped_column(String(64), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sandbox_type: Mapped[str] = mapped_column(String(32), nullable=False)
    image_tag: Mapped[str] = mapped_column(String(128), nullable=False)
    image_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    checks_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    obligation_rechecks_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    has_regressions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    patch: Mapped[PatchTable] = relationship("PatchTable", back_populates="verification_runs")
    evidence_report: Mapped[EvidenceReportTable | None] = relationship("EvidenceReportTable", back_populates="verification_run", uselist=False, cascade="all, delete-orphan")


class EvidenceReportTable(Base):
    """Persisted structured evidence report and markdown summary."""
    __tablename__ = "evidence_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    verification_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("verification_runs.id", ondelete="CASCADE"), nullable=False)
    report_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False)

    verification_run: Mapped[VerificationRunTable] = relationship("VerificationRunTable", back_populates="evidence_report")


class AgentRunTable(Base):
    """Persisted record of an LLM agent execution run."""
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain_id: Mapped[str] = mapped_column(String(64), ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_repair_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    tool_calls_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposed_patch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposed_patch_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan_approved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issue_analysis_json: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    task_plan_json: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    patch_proposal_json: Mapped[Dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class GitHubWebhookDeliveryTable(Base):
    """Track processed GitHub webhook delivery IDs for idempotency and auditing."""
    __tablename__ = "github_webhook_deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="processed", nullable=False)


class PublicationApprovalTable(Base):
    """Stores human approval decisions bound to exact patch and target."""

    __tablename__ = "publication_approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repository_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    repository_name: Mapped[str] = mapped_column(String(128), nullable=False)
    repository_id: Mapped[str] = mapped_column(String(256), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chain_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    patch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    patch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    base_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    target_base_branch: Mapped[str] = mapped_column(String(128), nullable=False)
    proposed_head_branch: Mapped[str] = mapped_column(String(256), nullable=False)
    verification_report_id: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    approver_identity: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="AWAITING_APPROVAL", nullable=False)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PublicationRunTable(Base):
    """Tracks publication executions and GitHub remote mutations."""

    __tablename__ = "publication_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    approval_id: Mapped[str] = mapped_column(String(64), ForeignKey("publication_approvals.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chain_id: Mapped[str] = mapped_column(String(64), nullable=False)
    repository_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    repository_name: Mapped[str] = mapped_column(String(128), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(256), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(128), nullable=False)
    base_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    head_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pull_request_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pull_request_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PublishedPullRequestTable(Base):
    """Stores permanent references to successfully published pull requests."""

    __tablename__ = "published_pull_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("publication_runs.id"), nullable=False)
    approval_id: Mapped[str] = mapped_column(String(64), ForeignKey("publication_approvals.id"), nullable=False)
    repository_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    repository_name: Mapped[str] = mapped_column(String(128), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    html_url: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    head_branch: Mapped[str] = mapped_column(String(256), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(128), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)


class BenchmarkRunTable(Base):
    """Stores benchmark experiment executions and aggregate metrics."""

    __tablename__ = "benchmark_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    baseline: Mapped[str] = mapped_column(String(64), nullable=False)
    corpus_id: Mapped[str] = mapped_column(String(64), nullable=False)
    total_chains: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_chains: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tasks: Mapped[int] = mapped_column(Integer, nullable=False)
    successful_tasks: Mapped[int] = mapped_column(Integer, nullable=False)
    regressions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    raw_results_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    executed_at: Mapped[str] = mapped_column(String(64), nullable=False)
