"""Create the notification_settings table.

Revision ID: 0010
Revises: 0009

Idempotent: the table is created only when missing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "notification_settings" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "notification_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(16), nullable=False),
            sa.Column("target", sa.String(512), nullable=False),
            sa.Column("events", sa.JSON(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_notification_settings_user_id", "notification_settings", ["user_id"])


def downgrade() -> None:
    if "notification_settings" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("notification_settings")
