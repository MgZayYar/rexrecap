"""Link videos to projects: nullable project_id on videos.

Revision ID: 0005
Revises: 0004

Idempotent: the column/constraint/index are added only when missing.
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


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("videos")}
    if "project_id" not in columns:
        op.add_column("videos", sa.Column("project_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_videos_project_id", "videos", "projects",
            ["project_id"], ["id"], ondelete="SET NULL",
        )
        op.create_index("ix_videos_project_id", "videos", ["project_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("videos")}
    if "project_id" in columns:
        op.drop_index("ix_videos_project_id", table_name="videos")
        op.drop_constraint("fk_videos_project_id", "videos", type_="foreignkey")
        op.drop_column("videos", "project_id")
