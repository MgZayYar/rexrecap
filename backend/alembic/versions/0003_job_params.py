"""Add params JSON to processing_jobs for per-job options.

Revision ID: 0003
Revises: 0002

Idempotent: the column is added only when missing. Stores worker options
such as the dubbing voice/provider so jobs stay self-describing without
a new table per job type.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "params" not in _column_names("processing_jobs"):
        with op.batch_alter_table("processing_jobs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("params", sa.JSON(), nullable=True))


def downgrade() -> None:
    if "params" in _column_names("processing_jobs"):
        with op.batch_alter_table("processing_jobs", schema=None) as batch_op:
            batch_op.drop_column("params")
