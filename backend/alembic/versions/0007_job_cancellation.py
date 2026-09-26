"""Job cancellation and worker heartbeats.

Revision ID: 0007
Revises: 0006

- Adds ``processing_jobs.cancel_requested``: the cooperative cancel flag a
  worker checks while a job runs.
- Adds the ``worker_heartbeats`` table: one row per worker process,
  refreshed while the worker is alive.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "cancel_requested" not in _column_names("processing_jobs"):
        op.add_column("processing_jobs",
                      sa.Column("cancel_requested", sa.Boolean(), nullable=False,
                                server_default=sa.false()))
    if "worker_heartbeats" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "worker_heartbeats",
            sa.Column("worker_id", sa.String(32), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("last_seen", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("current_job_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("worker_id"),
        )


def downgrade() -> None:
    if "worker_heartbeats" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("worker_heartbeats")
    if "cancel_requested" in _column_names("processing_jobs"):
        op.drop_column("processing_jobs", "cancel_requested")
