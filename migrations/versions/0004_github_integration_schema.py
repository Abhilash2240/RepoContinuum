"""Schema migration adding github_webhook_deliveries table for idempotent webhook tracking.

Revision ID: 0004_github_integration_schema
Revises: 0003_agent_run_schema
Create Date: 2026-11-21 18:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004_github_integration_schema"
down_revision: Union[str, None] = "0003_agent_run_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_webhook_deliveries",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("delivery_id", sa.String(length=128), unique=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("processed_at", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="processed"),
    )
    op.create_index(
        "ix_github_webhook_deliveries_delivery_id",
        "github_webhook_deliveries",
        ["delivery_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_github_webhook_deliveries_delivery_id", table_name="github_webhook_deliveries")
    op.drop_table("github_webhook_deliveries")
