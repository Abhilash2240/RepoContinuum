"""Initial schema for task chains, dependencies, obligations, checkpoints, and audit events.

Revision ID: 0001_initial_task_chain_schema
Revises:
Create Date: 2026-11-21 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_task_chain_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Task Chains table
    op.create_table(
        "task_chains",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("repository_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )

    # 2. Maintenance Tasks table
    op.create_table(
        "maintenance_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), sa.ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("candidate_files", sa.JSON(), nullable=False),
        sa.Column("candidate_symbols", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )

    # 3. Task Dependencies table
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), sa.ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("predecessor_task_id", sa.String(length=64), nullable=False),
        sa.Column("successor_task_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("chain_id", "predecessor_task_id", "successor_task_id", name="uq_task_dependency"),
    )

    # 4. Obligations table
    op.create_table(
        "obligations",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), sa.ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_task_id", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verifier_ref", sa.String(length=255), nullable=True),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )

    # 5. Checkpoints table
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), sa.ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_number", sa.Integer(), nullable=False),
        sa.Column("state_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )

    # 6. Audit Events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), sa.ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("checkpoints")
    op.drop_table("obligations")
    op.drop_table("task_dependencies")
    op.drop_table("maintenance_tasks")
    op.drop_table("task_chains")
