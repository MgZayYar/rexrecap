"""Add output_path to processing_jobs for jobs that produce files.

Revision ID: 0002
Revises: 0001

Idempotent: the column is added only when missing, so `alembic upgrade head`
is safe on databases at any earlier state.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "output_path" not in _column_names("processing_jobs"):
        with op.batch_alter_table("processing_jobs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("output_path", sa.Text(), nullable=True))


def downgrade() -> None:
    if "output_path" in _column_names("processing_jobs"):
        with op.batch_alter_table("processing_jobs", schema=None) as batch_op:
            batch_op.drop_column("output_path")
