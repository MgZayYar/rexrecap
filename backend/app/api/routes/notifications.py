"""Notification settings REST API: manage email/webhook job alerts."""

import asyncio

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.notification_setting import (
    NOTIFICATION_EVENTS,
    NotificationSetting,
)
from app.services.notifications import send_test_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str
    target: str
    events: list[str]
    enabled: bool


class NotificationSettingCreate(BaseModel):
    channel: str = Field(pattern=r"^(email|webhook)$")
    target: str = Field(min_length=3, max_length=512)
    events: list[str] = Field(default_factory=lambda: list(NOTIFICATION_EVENTS))
    enabled: bool = True

    @field_validator("target")
    @classmethod
    def _validate_target(cls, value: str, info) -> str:
        channel = (info.data or {}).get("channel")
        value = value.strip()
        if channel == "email":
            from pydantic import EmailStr, TypeAdapter
            try:
                TypeAdapter(EmailStr).validate_python(value)
            except ValueError:
                raise ValueError("target must be a valid email address")
        elif channel == "webhook":
            if not value.startswith(("http://", "https://")):
                raise ValueError("target must be an http(s) URL")
        return value

    @field_validator("events")
    @classmethod
    def _validate_events(cls, value: list[str]) -> list[str]:
        unknown = [e for e in value if e not in NOTIFICATION_EVENTS]
        if unknown:
            raise ValueError(f"Unknown events: {unknown}")
        if not value:
            raise ValueError("At least one event is required")
        return sorted(set(value))


class NotificationSettingUpdate(BaseModel):
    target: str | None = Field(default=None, min_length=3, max_length=512)
    events: list[str] | None = None
    enabled: bool | None = None

    @field_validator("events")
    @classmethod
    def _validate_events(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        unknown = [e for e in value if e not in NOTIFICATION_EVENTS]
        if unknown:
            raise ValueError(f"Unknown events: {unknown}")
        if not value:
            raise ValueError("At least one event is required")
        return sorted(set(value))


def _owned(db: DbSession, setting_id: int, user_id: int) -> NotificationSetting:
    setting = db.scalar(
        select(NotificationSetting).where(
            NotificationSetting.id == setting_id,
            NotificationSetting.user_id == user_id))
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Notification setting not found")
    return setting


@router.get("/settings", response_model=list[NotificationSettingResponse])
def list_settings(current_user: CurrentUser, db: DbSession):
    return db.scalars(
        select(NotificationSetting)
        .where(NotificationSetting.user_id == current_user.id)
        .order_by(NotificationSetting.created_at)
    ).all()


@router.post("/settings", response_model=NotificationSettingResponse,
             status_code=status.HTTP_201_CREATED)
def create_setting(payload: NotificationSettingCreate,
                   current_user: CurrentUser, db: DbSession):
    setting = NotificationSetting(
        user_id=current_user.id, channel=payload.channel,
        target=payload.target.strip(), events=payload.events,
        enabled=payload.enabled)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.patch("/settings/{setting_id}", response_model=NotificationSettingResponse)
def update_setting(setting_id: int, payload: NotificationSettingUpdate,
                   current_user: CurrentUser, db: DbSession):
    setting = _owned(db, setting_id, current_user.id)
    if payload.target is not None:
        target = payload.target.strip()
        if setting.channel == "webhook":
            if not target.startswith(("http://", "https://")):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    detail="Webhook target must be an http(s) URL")
        elif setting.channel == "email":
            from pydantic import EmailStr, TypeAdapter
            try:
                TypeAdapter(EmailStr).validate_python(target)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    detail="Target must be a valid email address")
        setting.target = target
    if payload.events is not None:
        setting.events = payload.events
    if payload.enabled is not None:
        setting.enabled = payload.enabled
    db.commit()
    db.refresh(setting)
    return setting


@router.delete("/settings/{setting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(setting_id: int, current_user: CurrentUser, db: DbSession):
    setting = _owned(db, setting_id, current_user.id)
    db.delete(setting)
    db.commit()


@router.post("/settings/{setting_id}/test")
async def test_setting(setting_id: int, current_user: CurrentUser, db: DbSession):
    setting = _owned(db, setting_id, current_user.id)
    try:
        await asyncio.to_thread(send_test_notification, setting.id, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Test notification failed: {exc}")
    return {"ok": True}
