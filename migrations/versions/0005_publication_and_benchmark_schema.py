"""Schema migration adding publication approvals, publication runs, published PRs, and benchmark runs.

Revision ID: 0005_publication_and_benchmark_schema
Revises: 0004_github_integration_schema
Create Date: 2026-11-21 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_publication_and_benchmark_schema"
down_revision: Union[str, None] = "0004_github_integration_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. publication_approvals
    op.create_table(
        "publication_approvals",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("repository_owner", sa.String(length=128), nullable=False),
        sa.Column("repository_name", sa.String(length=128), nullable=False),
        sa.Column("repository_id", sa.String(length=256), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("chain_id", sa.String(length=64), nullable=False),
        sa.Column("patch_id", sa.String(length=64), nullable=False),
        sa.Column("patch_hash", sa.String(length=64), nullable=False),
        sa.Column("base_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("target_base_branch", sa.String(length=128), nullable=False),
        sa.Column("proposed_head_branch", sa.String(length=256), nullable=False),
        sa.Column("verification_report_id", sa.String(length=64), nullable=False),
        sa.Column("verification_run_id", sa.String(length=64), nullable=False),
        sa.Column("approver_identity", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="AWAITING_APPROVAL"),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("approved_at", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.String(length=64), nullable=True),
        sa.Column("approval_metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_publication_approvals_task_id", "publication_approvals", ["task_id"])
    op.create_index("ix_publication_approvals_chain_id", "publication_approvals", ["chain_id"])

    # 2. publication_runs
    op.create_table(
        "publication_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("approval_id", sa.String(length=64), sa.ForeignKey("publication_approvals.id"), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("chain_id", sa.String(length=64), nullable=False),
        sa.Column("repository_owner", sa.String(length=128), nullable=False),
        sa.Column("repository_name", sa.String(length=128), nullable=False),
        sa.Column("head_branch", sa.String(length=256), nullable=False),
        sa.Column("base_branch", sa.String(length=128), nullable=False),
        sa.Column("base_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("head_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("pull_request_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
    )

    # 3. published_pull_requests
    op.create_table(
        "published_pull_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("publication_runs.id"), nullable=False),
        sa.Column("approval_id", sa.String(length=64), sa.ForeignKey("publication_approvals.id"), nullable=False),
        sa.Column("repository_owner", sa.String(length=128), nullable=False),
        sa.Column("repository_name", sa.String(length=128), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("html_url", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("head_branch", sa.String(length=256), nullable=False),
        sa.Column("base_branch", sa.String(length=128), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )

    # 4. benchmark_runs
    op.create_table(
        "benchmark_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("baseline", sa.String(length=64), nullable=False),
        sa.Column("corpus_id", sa.String(length=64), nullable=False),
        sa.Column("total_chains", sa.Integer(), nullable=False),
        sa.Column("completed_chains", sa.Integer(), nullable=False),
        sa.Column("total_tasks", sa.Integer(), nullable=False),
        sa.Column("successful_tasks", sa.Integer(), nullable=False),
        sa.Column("regressions_count", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("raw_results_path", sa.String(length=512), nullable=True),
        sa.Column("executed_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("benchmark_runs")
    op.drop_table("published_pull_requests")
    op.drop_table("publication_runs")
    op.drop_index("ix_publication_approvals_chain_id", table_name="publication_approvals")
    op.drop_index("ix_publication_approvals_task_id", table_name="publication_approvals")
    op.drop_table("publication_approvals")
