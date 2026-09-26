"""Alembic migration environment for the RexCrop backend.

Reads the database URL from app.core.config (same source the app uses).
Relative SQLite paths are resolved against the backend directory so
migrations behave the same regardless of the working directory.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import DATABASE_URL  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models import (  # noqa: E402,F401 - register model metadata
    ProcessingJob,
    Project,
    Transcript,
    Translation,
    User,
    Video,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_database_url(url: str) -> str:
    # Keep relative SQLite files anchored to the backend directory.
    if url.startswith("sqlite:///./") or url.startswith("sqlite:///../"):
        relative = url.split("sqlite:///", 1)[1]
        return f"sqlite:///{(BACKEND_DIR / relative).resolve()}"
    return url


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_resolve_database_url(DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _resolve_database_url(DATABASE_URL)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
