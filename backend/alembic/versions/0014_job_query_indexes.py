"""Composite indexes for the hot job queries.

- processing_jobs(video_id, created_at): per-video job lists, newest first.
- processing_jobs(status, created_at): the runner's oldest-queued claim and
  the status-filtered job list.
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    from sqlalchemy import inspect
    return name in inspect(bind).get_table_names()


def _index_exists(bind, table: str, name: str) -> bool:
    from sqlalchemy import inspect
    return any(idx["name"] == name for idx in inspect(bind).get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "processing_jobs"):
        return
    if not _index_exists(bind, "processing_jobs", "ix_processing_jobs_video_created"):
        op.create_index("ix_processing_jobs_video_created", "processing_jobs",
                        ["video_id", "created_at"])
    if not _index_exists(bind, "processing_jobs", "ix_processing_jobs_status_created"):
        op.create_index("ix_processing_jobs_status_created", "processing_jobs",
                        ["status", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "processing_jobs"):
        return
    if _index_exists(bind, "processing_jobs", "ix_processing_jobs_status_created"):
        op.drop_index("ix_processing_jobs_status_created", table_name="processing_jobs")
    if _index_exists(bind, "processing_jobs", "ix_processing_jobs_video_created"):
        op.drop_index("ix_processing_jobs_video_created", table_name="processing_jobs")
