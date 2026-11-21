"""Schema migration adding patches, verification runs, and evidence reports.

Revision ID: 0002_patch_and_verification_schema
Revises: 0001_initial_task_chain_schema
Create Date: 2026-11-21 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_patch_and_verification_schema"
down_revision: Union[str, None] = "0001_initial_task_chain_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Patches table
    op.create_table(
        "patches",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("repository_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=64), sa.ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("patch_hash", sa.String(length=64), nullable=False),
        sa.Column("diff_content", sa.Text(), nullable=False),
        sa.Column("changed_paths", sa.JSON(), nullable=False),
        sa.Column("total_added_lines", sa.Integer(), nullable=False),
        sa.Column("total_removed_lines", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )

    # 2. Verification Runs table
    op.create_table(
        "verification_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("patch_id", sa.String(length=64), sa.ForeignKey("patches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("chain_id", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("sandbox_type", sa.String(length=32), nullable=False),
        sa.Column("image_tag", sa.String(length=128), nullable=False),
        sa.Column("image_digest", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("checks_json", sa.JSON(), nullable=False),
        sa.Column("obligation_rechecks_json", sa.JSON(), nullable=False),
        sa.Column("has_regressions", sa.Boolean(), nullable=False),
    )

    # 3. Evidence Reports table
    op.create_table(
        "evidence_reports",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("verification_run_id", sa.String(length=64), sa.ForeignKey("verification_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("summary_markdown", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("evidence_reports")
    op.drop_table("verification_runs")
    op.drop_table("patches")
