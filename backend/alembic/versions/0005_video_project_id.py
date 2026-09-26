"""Link videos to projects: nullable project_id on videos.

Revision ID: 0005
Revises: 0004

Idempotent: the column, foreign key, and index are each added only when
missing. Uses batch mode because SQLite cannot ALTER constraints in place.
Deleting a project sets its videos' project_id to NULL (videos survive).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _fk_names(table: str) -> set[str]:
    return {fk["name"] for fk in sa.inspect(op.get_bind()).get_foreign_keys(table) if fk["name"]}


def _index_names(table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(table) if ix["name"]}


def upgrade() -> None:
    with op.batch_alter_table("videos", schema=None) as batch_op:
        if "project_id" not in _column_names("videos"):
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        if "fk_videos_project_id" not in _fk_names("videos"):
            batch_op.create_foreign_key(
                "fk_videos_project_id", "projects",
                ["project_id"], ["id"], ondelete="SET NULL",
            )
        if "ix_videos_project_id" not in _index_names("videos"):
            batch_op.create_index("ix_videos_project_id", ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("videos", schema=None) as batch_op:
        if "ix_videos_project_id" in _index_names("videos"):
            batch_op.drop_index("ix_videos_project_id")
        if "fk_videos_project_id" in _fk_names("videos"):
            batch_op.drop_constraint("fk_videos_project_id", type_="foreignkey")
        if "project_id" in _column_names("videos"):
            batch_op.drop_column("project_id")
