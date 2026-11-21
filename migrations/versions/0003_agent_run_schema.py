"""Schema migration adding agent_runs table for LLM agent observability and audit tracking.

Revision ID: 0003_agent_run_schema
Revises: 0002_patch_and_verification_schema
Create Date: 2026-11-21 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_agent_run_schema"
down_revision: Union[str, None] = "0002_patch_and_verification_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("chain_id", sa.String(length=64), sa.ForeignKey("task_chains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_repair_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("tool_calls_json", sa.JSON(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_category", sa.String(length=64), nullable=True),
        sa.Column("proposed_patch_id", sa.String(length=64), nullable=True),
        sa.Column("proposed_patch_hash", sa.String(length=64), nullable=True),
        sa.Column("verification_run_id", sa.String(length=64), nullable=True),
        sa.Column("plan_approved_by", sa.String(length=64), nullable=True),
        sa.Column("plan_approved_at", sa.String(length=64), nullable=True),
        sa.Column("issue_analysis_json", sa.JSON(), nullable=True),
        sa.Column("task_plan_json", sa.JSON(), nullable=True),
        sa.Column("patch_proposal_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
