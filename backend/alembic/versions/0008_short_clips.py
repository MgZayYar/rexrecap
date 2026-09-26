"""Create the short_clips table for highlight-clip generation.

Revision ID: 0008
Revises: 0007

Idempotent: the table is created only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "short_clips" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "short_clips",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("start_time", sa.Float(), nullable=False),
            sa.Column("end_time", sa.Float(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("output_path", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_short_clips_video_id", "short_clips", ["video_id"])
        op.create_index("ix_short_clips_job_id", "short_clips", ["job_id"])


def downgrade() -> None:
    if "short_clips" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("short_clips")
