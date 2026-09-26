"""Database schema management.

The application owns its schema through Alembic migrations (see
``backend/alembic``). On startup we run ``alembic upgrade head`` so a fresh
checkout and an existing database both converge to the current schema
without destroying data.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger("rexcrop")

BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    """Apply pending Alembic migrations to the configured database."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    logger.info("Applying database migrations")
    command.upgrade(cfg, "head")
