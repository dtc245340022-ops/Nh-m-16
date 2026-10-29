from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import URL, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import Conference, PresentationSession
from security import CurrentUser, OrganizerUser

router = APIRouter(prefix="/api/sessions", tags=["Phiên trình bày"])

engine = create_engine(URL.create("sqlite", database=str(DATABASE_PATH)))


@event.listens_for(engine, "connect")
def _enable_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conference_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    room: str | None = Field(default=None, max_length=100)
    starts_at: datetime
    ends_at: datetime

    @field_validator("title", "room")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field must not be empty")
        return value

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class SessionOutput(SessionInput):
    model_config = ConfigDict(from_attributes=True)

    id: int


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "FOREIGN KEY constraint failed" in str(error.orig):
            raise HTTPException(
                status_code=409,
                detail="Không thể xóa phiên đang được bài báo sử dụng.",
            ) from error
        raise HTTPException(
            status_code=422,
            detail="Dữ liệu phiên không hợp lệ hoặc khóa ngoại không tồn tại.",
        ) from error


def _get_session(db: Session, session_id: int) -> PresentationSession:
    presentation = db.get(PresentationSession, session_id)
    if presentation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên trình bày.")
    return presentation


def _validate_session(
    db: Session, payload: SessionInput, current_id: int | None = None
) -> None:
    conference = db.get(Conference, payload.conference_id)
    if conference is None:
        raise HTTPException(status_code=422, detail="Hội nghị không tồn tại.")
    if (
        payload.starts_at < conference.starts_at
        or payload.ends_at > conference.ends_at
    ):
        raise HTTPException(
            status_code=422,
            detail="Thời gian phiên phải nằm trong thời gian diễn ra hội nghị.",
        )

    if payload.room is not None:
        overlapping = db.scalar(
            select(PresentationSession.id).where(
                PresentationSession.conference_id == payload.conference_id,
                PresentationSession.room == payload.room,
                PresentationSession.starts_at < payload.ends_at,
                PresentationSession.ends_at > payload.starts_at,
                PresentationSession.id != (current_id or 0),
            )
        )
        if overlapping is not None:
            raise HTTPException(
                status_code=409,
                detail="Phòng đã có phiên trình bày trùng thời gian.",
            )


@router.get("", response_model=list[SessionOutput])
def list_sessions(
    db: DbSession, current_user: CurrentUser, conference_id: int | None = None
):
    query = select(PresentationSession).order_by(PresentationSession.id)
    if conference_id is not None:
        query = query.where(PresentationSession.conference_id == conference_id)
    return db.scalars(query).all()


@router.post("", response_model=SessionOutput, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionInput, db: DbSession, current_user: OrganizerUser
):
    _validate_session(db, payload)
    presentation = PresentationSession(**payload.model_dump())
    db.add(presentation)
    _save(db)
    db.refresh(presentation)
    return presentation


@router.get("/{session_id}", response_model=SessionOutput)
def get_session(
    session_id: int, db: DbSession, current_user: CurrentUser
):
    return _get_session(db, session_id)


@router.put("/{session_id}", response_model=SessionOutput)
def update_session(
    session_id: int,
    payload: SessionInput,
    db: DbSession,
    current_user: OrganizerUser,
):
    presentation = _get_session(db, session_id)
    _validate_session(db, payload, current_id=session_id)
    for field, value in payload.model_dump().items():
        setattr(presentation, field, value)
    _save(db)
    db.refresh(presentation)
    return presentation


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int, db: DbSession, current_user: OrganizerUser
):
    presentation = _get_session(db, session_id)
    db.delete(presentation)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
