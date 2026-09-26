"""Create batch_runs and batch_run_items tables.

Revision ID: 0012
Revises: 0011

Idempotent: tables are created only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    names = set(inspector.get_table_names())
    if "batch_runs" not in names:
        op.create_table(
            "batch_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(255), nullable=False),
            sa.Column("job_type", sa.String(50), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_batch_runs_user_id", "batch_runs", ["user_id"])
    if "batch_run_items" not in names:
        op.create_table(
            "batch_run_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("batch_run_id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["batch_run_id"], ["batch_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_batch_run_items_batch_run_id", "batch_run_items", ["batch_run_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    names = set(inspector.get_table_names())
    if "batch_run_items" in names:
        op.drop_table("batch_run_items")
    if "batch_runs" in names:
        op.drop_table("batch_runs")
