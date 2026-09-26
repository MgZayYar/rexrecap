"""Baseline schema: users, projects, videos, processing_jobs, transcripts, translations.

Revision ID: 0001
Revises: (none)

This migration is idempotent: every table and index is created only when
missing, so `alembic upgrade head` is safe on databases that were created
by the previous `Base.metadata.create_all()` bootstrap. It never drops or
alters existing tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def _create_table_if_missing(name: str, *columns: sa.Column, **kwargs) -> None:
    if name not in _table_names():
        op.create_table(name, *columns, **kwargs)


def _create_index_if_missing(table: str, name: str, columns: list[str], unique: bool = False) -> None:
    if name not in _index_names(table):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_index(name, columns, unique=unique)


def upgrade() -> None:
    _create_table_if_missing(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_missing("users", "ix_users_email", ["email"], unique=True)

    _create_table_if_missing(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_missing("projects", "ix_projects_user_id", ["user_id"])

    _create_table_if_missing(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )
    _create_index_if_missing("videos", "ix_videos_user_id", ["user_id"])

    _create_table_if_missing(
        "processing_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_missing("processing_jobs", "ix_processing_jobs_status", ["status"])
    _create_index_if_missing("processing_jobs", "ix_processing_jobs_video_id", ["video_id"])

    _create_table_if_missing(
        "transcripts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index_if_missing("transcripts", "ix_transcripts_video_id", ["video_id"], unique=True)

    _create_table_if_missing(
        "translations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transcript_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("target_language", sa.String(length=16), nullable=False),
        sa.Column("target_language_name", sa.String(length=80), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["processing_jobs.id"]),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transcript_id", "target_language", name="uq_translation_language"),
    )
    _create_index_if_missing("translations", "ix_translations_job_id", ["job_id"], unique=True)
    _create_index_if_missing("translations", "ix_translations_transcript_id", ["transcript_id"])


def downgrade() -> None:
    # The baseline downgrade drops every table. Only run it against databases
    # that were created by this migration chain, never against a database
    # that predates Alembic.
    op.drop_table("translations")
    op.drop_table("transcripts")
    op.drop_table("processing_jobs")
    op.drop_table("videos")
    op.drop_table("projects")
    op.drop_table("users")
