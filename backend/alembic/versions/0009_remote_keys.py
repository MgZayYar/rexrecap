"""Track object-storage keys for synced job outputs and clips.

Revision ID: 0009
Revises: 0008

Idempotent: columns are added only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column_if_missing("processing_jobs", sa.Column("output_remote_key", sa.Text(), nullable=True))
    _add_column_if_missing("short_clips", sa.Column("remote_key", sa.Text(), nullable=True))


def downgrade() -> None:
    for table, name in (("processing_jobs", "output_remote_key"), ("short_clips", "remote_key")):
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        if name in existing:
            op.drop_column(table, name)
