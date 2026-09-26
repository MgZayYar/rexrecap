"""Create the upload_sessions table for resumable uploads.

Revision ID: 0006
Revises: 0005

Idempotent: the table is created only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "upload_sessions" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "upload_sessions",
            sa.Column("id", sa.String(32), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("temp_filename", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("total_bytes", sa.Integer(), nullable=False),
            sa.Column("received_bytes", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("temp_filename"),
        )
        op.create_index("ix_upload_sessions_user_id", "upload_sessions", ["user_id"])
        op.create_index("ix_upload_sessions_status", "upload_sessions", ["status"])


def downgrade() -> None:
    if "upload_sessions" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("upload_sessions")
