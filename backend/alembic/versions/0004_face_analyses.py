"""Create the face_analyses table.

Revision ID: 0004
Revises: 0003

Idempotent: the table is created only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "face_analyses" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "face_analyses",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("video_id"),
            sa.UniqueConstraint("job_id"),
        )
        op.create_index("ix_face_analyses_video_id", "face_analyses", ["video_id"], unique=True)


def downgrade() -> None:
    if "face_analyses" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("face_analyses")
