from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import URL, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import Conference
from security import CurrentUser, OrganizerUser

router = APIRouter(prefix="/api/conferences", tags=["Hội nghị"])

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


class ConferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    venue: str | None = Field(default=None, max_length=255)
    starts_at: datetime
    ends_at: datetime
    submission_deadline: datetime
    review_deadline: datetime
    registration_deadline: datetime

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        return value

    @model_validator(mode="after")
    def validate_dates(self):
        date_fields = (
            "starts_at",
            "ends_at",
            "submission_deadline",
            "review_deadline",
            "registration_deadline",
        )
        for field in date_fields:
            value = getattr(self, field)
            if value.tzinfo is not None:
                setattr(self, field, value.astimezone(UTC).replace(tzinfo=None))

        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        for field in ("submission_deadline", "review_deadline", "registration_deadline"):
            if getattr(self, field) >= self.starts_at:
                raise ValueError(f"{field} must be earlier than starts_at")
        return self


class ConferenceOutput(ConferenceInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int


DbSession = Annotated[Session, Depends(get_db)]


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Dữ liệu không hợp lệ hoặc người tạo không tồn tại.",
        ) from error


@router.get("", response_model=list[ConferenceOutput])
def list_conferences(
    db: DbSession,
    current_user: CurrentUser,
):
    return db.scalars(select(Conference).order_by(Conference.id)).all()


@router.get("/{conference_id}", response_model=ConferenceOutput)
def get_conference(
    conference_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    conference = db.get(Conference, conference_id)
    if conference is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội nghị.")
    return conference


@router.post(
    "",
    response_model=ConferenceOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_conference(
    payload: ConferenceInput, db: DbSession, current_user: OrganizerUser
):
    conference = Conference(**payload.model_dump(), created_by=current_user.id)
    db.add(conference)
    _save(db)
    db.refresh(conference)
    return conference


@router.put("/{conference_id}", response_model=ConferenceOutput)
def update_conference(
    conference_id: int,
    payload: ConferenceInput,
    db: DbSession,
    current_user: OrganizerUser,
):
    conference = db.get(Conference, conference_id)
    if conference is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội nghị.")
    for field, value in payload.model_dump().items():
        setattr(conference, field, value)
    _save(db)
    db.refresh(conference)
    return conference


@router.delete("/{conference_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conference(
    conference_id: int, db: DbSession, current_user: OrganizerUser
):
    conference = db.get(Conference, conference_id)
    if conference is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội nghị.")
    db.delete(conference)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
