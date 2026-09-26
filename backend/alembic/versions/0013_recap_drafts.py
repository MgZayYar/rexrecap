"""Create the recap_drafts table.

Revision ID: 0013
Revises: 0012

Idempotent: the table is created only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "recap_drafts" not in inspector.get_table_names():
        op.create_table(
            "recap_drafts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("video_id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.Integer(), nullable=False),
            sa.Column("content", sa.JSON(), nullable=False),
            sa.Column("model", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_recap_drafts_video_id", "recap_drafts", ["video_id"])


def downgrade() -> None:
    if "recap_drafts" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("recap_drafts")
