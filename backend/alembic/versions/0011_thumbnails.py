"""Create the thumbnails table and add videos.thumbnail_path.

Revision ID: 0011
Revises: 0010

Idempotent: the table is created only when missing and the column is added
only when absent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "thumbnails" not in inspector.get_table_names():
        op.create_table(
            "thumbnails",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("path", sa.String(255), nullable=False),
            sa.Column("timestamp", sa.Float(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_thumbnails_video_id", "thumbnails", ["video_id"])
    video_columns = {c["name"] for c in inspector.get_columns("videos")}
    if "thumbnail_path" not in video_columns:
        with op.batch_alter_table("videos") as batch_op:
            batch_op.add_column(sa.Column("thumbnail_path", sa.String(255), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "thumbnails" in inspector.get_table_names():
        op.drop_table("thumbnails")
    video_columns = {c["name"] for c in inspector.get_columns("videos")}
    if "thumbnail_path" in video_columns:
        with op.batch_alter_table("videos") as batch_op:
            batch_op.drop_column("thumbnail_path")
