from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import URL, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import Conference, Registration, User
from security import CurrentUser, require_roles

router = APIRouter(prefix="/api/registrations", tags=["Đăng ký"])

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
RegistrationStatus = Literal["registered", "cancelled", "attended"]


class RegistrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conference_id: int = Field(gt=0)
    status: RegistrationStatus = "registered"


class RegistrationOutput(RegistrationInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    registered_at: datetime


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "UNIQUE constraint failed" not in str(error.orig):
            raise HTTPException(
                status_code=422,
                detail="Dữ liệu đăng ký không hợp lệ hoặc khóa ngoại không tồn tại.",
            ) from error
        raise HTTPException(
            status_code=409,
            detail="Tài khoản đã đăng ký hội nghị này.",
        ) from error


def _validate_registration(
    db: Session, payload: RegistrationInput, user_id: int
) -> None:
    conference = db.get(Conference, payload.conference_id)
    if conference is None:
        raise HTTPException(status_code=422, detail="Hội nghị không tồn tại.")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=422, detail="Tài khoản không tồn tại.")
    if payload.status == "registered":
        deadline = conference.registration_deadline
        if deadline.tzinfo is not None:
            deadline = deadline.astimezone(UTC).replace(tzinfo=None)
        if datetime.now(UTC).replace(tzinfo=None) > deadline:
            raise HTTPException(
                status_code=422,
                detail="Đã hết hạn đăng ký tham dự hội nghị.",
            )


def _get_registration(db: Session, registration_id: int) -> Registration:
    registration = db.get(Registration, registration_id)
    if registration is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký.")
    return registration


@router.get("", response_model=list[RegistrationOutput])
def list_registrations(
    db: DbSession,
    current_user: CurrentUser,
    conference_id: int | None = None,
    user_id: int | None = None,
):
    query = select(Registration).order_by(Registration.id)
    if current_user.role == "author":
        query = query.where(Registration.user_id == current_user.id)
    elif current_user.role not in ("admin", "organizer"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem đăng ký.")
    if conference_id is not None:
        query = query.where(Registration.conference_id == conference_id)
    if user_id is not None and current_user.role in ("admin", "organizer"):
        query = query.where(Registration.user_id == user_id)
    return db.scalars(query).all()


@router.post(
    "",
    response_model=RegistrationOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_registration(
    payload: RegistrationInput,
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles("author"))],
):
    registration_data = payload.model_dump()
    registration_data["user_id"] = current_user.id
    _validate_registration(db, payload, user_id=current_user.id)
    duplicate = db.scalar(
        select(Registration.id).where(
            Registration.conference_id == payload.conference_id,
            Registration.user_id == current_user.id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="Tài khoản đã đăng ký hội nghị này.",
        )
    registration = Registration(**registration_data)
    db.add(registration)
    _save(db)
    db.refresh(registration)
    return registration


@router.put("/{registration_id}", response_model=RegistrationOutput)
def update_registration(
    registration_id: int,
    payload: RegistrationInput,
    db: DbSession,
    current_user: CurrentUser,
):
    registration = _get_registration(db, registration_id)
    if current_user.role not in ("admin", "organizer", "author"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền sửa đăng ký.")
    if current_user.role == "author" and registration.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký.")
    if current_user.role == "author" and payload.status == "attended":
        raise HTTPException(
            status_code=403,
            detail="Người tham dự không thể tự xác nhận trạng thái đã tham dự.",
        )
    _validate_registration(db, payload, user_id=registration.user_id)
    registration.conference_id = payload.conference_id
    registration.status = payload.status
    _save(db)
    db.refresh(registration)
    return registration


@router.delete(
    "/{registration_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_registration(
    registration_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    registration = _get_registration(db, registration_id)
    if current_user.role not in ("admin", "organizer", "author"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa đăng ký.")
    if current_user.role == "author" and registration.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký.")
    db.delete(registration)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
