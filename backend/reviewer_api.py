from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import URL, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import ReviewerProfile, ReviewAssignment, User
from security import CurrentUser, OrganizerUser

router = APIRouter(prefix="/api/reviewers", tags=["Phản biện"])

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


class ReviewerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    expertise: str = Field(min_length=1)
    max_assignments: int = Field(default=5, gt=0)

    @field_validator("expertise")
    @classmethod
    def validate_expertise(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Chuyên môn không được để trống.")
        return value


class ReviewerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expertise: str = Field(min_length=1)
    max_assignments: int = Field(gt=0)

    @field_validator("expertise")
    @classmethod
    def validate_expertise(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Chuyên môn không được để trống.")
        return value


class ReviewerOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    expertise: str
    max_assignments: int


def _reviewer_output(user: User, profile: ReviewerProfile) -> ReviewerOutput:
    return ReviewerOutput(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        expertise=profile.expertise,
        max_assignments=profile.max_assignments,
    )


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Hồ sơ phản biện đã tồn tại hoặc đang được sử dụng.",
        ) from error


@router.get("", response_model=list[ReviewerOutput])
def list_reviewers(db: DbSession, current_user: CurrentUser):
    query = select(User, ReviewerProfile).join(
        ReviewerProfile, ReviewerProfile.user_id == User.id
    )
    if current_user.role == "reviewer":
        query = query.where(User.id == current_user.id)
    elif current_user.role not in ("admin", "organizer"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem hồ sơ phản biện.")
    rows = db.execute(query.order_by(User.id))
    return [_reviewer_output(user, profile) for user, profile in rows]


@router.post(
    "",
    response_model=ReviewerOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_reviewer(
    payload: ReviewerInput, db: DbSession, current_user: OrganizerUser
):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=422, detail="Tài khoản phản biện không tồn tại.")
    if user.role != "reviewer":
        raise HTTPException(status_code=422, detail="Tài khoản không có vai trò phản biện.")
    if db.get(ReviewerProfile, payload.user_id) is not None:
        raise HTTPException(status_code=409, detail="Hồ sơ phản biện đã tồn tại.")

    profile = ReviewerProfile(
        user_id=payload.user_id,
        expertise=payload.expertise,
        max_assignments=payload.max_assignments,
    )
    db.add(profile)
    _save(db)
    return _reviewer_output(user, profile)


@router.put("/{reviewer_id}", response_model=ReviewerOutput)
def update_reviewer(
    reviewer_id: int,
    payload: ReviewerUpdate,
    db: DbSession,
    current_user: OrganizerUser,
):
    profile = db.get(ReviewerProfile, reviewer_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ phản biện.")
    assigned_count = db.scalar(
        select(func.count()).select_from(ReviewAssignment).where(
            ReviewAssignment.reviewer_id == reviewer_id,
            ReviewAssignment.status.in_(("assigned", "in_progress")),
        )
    )
    if payload.max_assignments < assigned_count:
        raise HTTPException(
            status_code=422,
            detail="Giới hạn phân công không thể thấp hơn số phân công đang hoạt động.",
        )

    profile.expertise = payload.expertise
    profile.max_assignments = payload.max_assignments
    _save(db)
    return _reviewer_output(db.get(User, reviewer_id), profile)


@router.delete("/{reviewer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reviewer(
    reviewer_id: int, db: DbSession, current_user: OrganizerUser
):
    profile = db.get(ReviewerProfile, reviewer_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ phản biện.")
    assignment_exists = db.scalar(
        select(ReviewAssignment.id).where(
            ReviewAssignment.reviewer_id == reviewer_id
        )
    )
    if assignment_exists is not None:
        raise HTTPException(
            status_code=409,
            detail="Không thể xóa hồ sơ phản biện đã có phân công.",
        )
    db.delete(profile)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
