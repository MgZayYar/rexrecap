"""Ownership-scoped project queries shared by API routes."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


def get_owned_project(db: Session, project_id: int, user_id: int) -> Project | None:
    """Return the project only when it belongs to the given user."""
    return db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))


def list_user_projects(db: Session, user_id: int) -> list[Project]:
    """Return the user's projects, newest first."""
    return list(
        db.scalars(select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc()))
    )
