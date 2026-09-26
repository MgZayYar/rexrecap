from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.project import Project
from app.models.video import Video
from app.repositories.projects import get_owned_project, list_user_projects
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.video import VideoResponse

router = APIRouter(prefix="/projects", tags=["projects"])


def _require_owned_project(project_id: int, current_user: CurrentUser, db: DbSession) -> Project:
    project = get_owned_project(db, project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, current_user: CurrentUser, db: DbSession) -> Project:
    project = Project(user_id=current_user.id, name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(current_user: CurrentUser, db: DbSession) -> list[Project]:
    return list_user_projects(db, current_user.id)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, current_user: CurrentUser, db: DbSession) -> Project:
    return _require_owned_project(project_id, current_user, db)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, payload: ProjectUpdate, current_user: CurrentUser, db: DbSession
) -> Project:
    project = _require_owned_project(project_id, current_user, db)
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.status is not None:
        project.status = payload.status
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, current_user: CurrentUser, db: DbSession) -> None:
    project = _require_owned_project(project_id, current_user, db)
    db.delete(project)
    db.commit()


@router.get("/{project_id}/videos", response_model=list[VideoResponse])
def list_project_videos(project_id: int, current_user: CurrentUser, db: DbSession) -> list[Video]:
    _require_owned_project(project_id, current_user, db)
    return list(db.scalars(
        select(Video)
        .where(Video.user_id == current_user.id, Video.project_id == project_id)
        .order_by(Video.created_at.desc())
    ))
