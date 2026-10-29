from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import URL, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import (
    Conference,
    Paper,
    PaperAuthor,
    Review,
    ReviewAssignment,
    ReviewerProfile,
)
from security import CurrentUser, OrganizerUser, ReviewerUser

assignment_router = APIRouter(
    prefix="/api/review-assignments", tags=["Phân công"]
)
review_router = APIRouter(prefix="/api/reviews", tags=["Đánh giá"])

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
AssignmentStatus = Literal["assigned", "in_progress", "completed", "declined"]
Recommendation = Literal["accept", "minor_revision", "major_revision", "reject"]


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: int = Field(gt=0)
    reviewer_id: int = Field(gt=0)
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def normalize_deadline(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value


class AssignmentUpdate(BaseModel):
    deadline: datetime
    status: AssignmentStatus

    @field_validator("deadline")
    @classmethod
    def normalize_deadline(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value


class AssignmentOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paper_id: int
    reviewer_id: int
    assigned_by: int
    deadline: datetime
    status: AssignmentStatus


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: int = Field(gt=0)
    comments: str = Field(min_length=1)
    recommendation: Recommendation
    score: int = Field(ge=1, le=5)

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nhận xét không được để trống.")
        return value


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comments: str = Field(min_length=1)
    recommendation: Recommendation
    score: int = Field(ge=1, le=5)

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nhận xét không được để trống.")
        return value


class ReviewOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    comments: str
    recommendation: Recommendation
    score: int
    submitted_at: datetime


def _save(db: Session, *, conflict_message: str | None = None) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if conflict_message is not None:
            raise HTTPException(status_code=409, detail=conflict_message) from error
        raise HTTPException(
            status_code=422,
            detail="Dữ liệu không hợp lệ hoặc khóa ngoại không tồn tại.",
        ) from error


def _get_assignment(db: Session, assignment_id: int) -> ReviewAssignment:
    assignment = db.get(ReviewAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân công phản biện.")
    return assignment


def _validate_deadline(db: Session, paper: Paper, deadline: datetime) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    if deadline <= now:
        raise HTTPException(status_code=422, detail="Hạn phản biện phải ở tương lai.")
    conference = db.get(Conference, paper.conference_id)
    if conference is None:
        raise HTTPException(status_code=422, detail="Hội nghị của bài báo không tồn tại.")
    if deadline > conference.review_deadline:
        raise HTTPException(
            status_code=422,
            detail="Hạn phản biện không được vượt quá hạn phản biện của hội nghị.",
        )


@assignment_router.get("", response_model=list[AssignmentOutput])
def list_assignments(
    db: DbSession,
    current_user: CurrentUser,
    paper_id: int | None = None,
    reviewer_id: int | None = None,
):
    query = select(ReviewAssignment).order_by(ReviewAssignment.id)
    if current_user.role == "reviewer":
        query = query.where(ReviewAssignment.reviewer_id == current_user.id)
    elif current_user.role not in ("admin", "organizer"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem phân công.")
    if paper_id is not None:
        query = query.where(ReviewAssignment.paper_id == paper_id)
    if reviewer_id is not None and current_user.role in ("admin", "organizer"):
        query = query.where(ReviewAssignment.reviewer_id == reviewer_id)
    return db.scalars(query).all()


@assignment_router.post(
    "",
    response_model=AssignmentOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: AssignmentCreate, db: DbSession, current_user: OrganizerUser
):
    paper = db.get(Paper, payload.paper_id)
    if paper is None:
        raise HTTPException(status_code=422, detail="Bài báo không tồn tại.")
    if db.get(PaperAuthor, (paper.id, payload.reviewer_id)) is not None:
        raise HTTPException(
            status_code=409,
            detail="Tác giả không được tự phản biện bài báo của mình.",
        )
    if paper.submitted_by == payload.reviewer_id:
        raise HTTPException(
            status_code=409,
            detail="Người gửi bài không được tự phản biện bài báo của mình.",
        )
    profile = db.get(ReviewerProfile, payload.reviewer_id)
    if profile is None:
        raise HTTPException(status_code=422, detail="Tài khoản chưa có hồ sơ phản biện.")
    if db.scalar(
        select(ReviewAssignment.id).where(
            ReviewAssignment.paper_id == payload.paper_id,
            ReviewAssignment.reviewer_id == payload.reviewer_id,
        )
    ) is not None:
        raise HTTPException(status_code=409, detail="Phản biện đã được phân công bài báo này.")
    active_count = db.scalar(
        select(func.count()).select_from(ReviewAssignment).where(
            ReviewAssignment.reviewer_id == payload.reviewer_id,
            ReviewAssignment.status.in_(("assigned", "in_progress")),
        )
    )
    if active_count >= profile.max_assignments:
        raise HTTPException(
            status_code=409,
            detail="Phản biện đã đạt số lượng phân công tối đa.",
        )
    _validate_deadline(db, paper, payload.deadline)

    assignment = ReviewAssignment(
        **payload.model_dump(), assigned_by=current_user.id
    )
    db.add(assignment)
    _save(
        db,
        conflict_message="Phản biện đã được phân công bài báo này.",
    )
    db.refresh(assignment)
    return assignment


@assignment_router.put("/{assignment_id}", response_model=AssignmentOutput)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: DbSession,
    current_user: OrganizerUser,
):
    assignment = _get_assignment(db, assignment_id)
    paper = db.get(Paper, assignment.paper_id)
    if paper is None:
        raise HTTPException(status_code=422, detail="Bài báo của phân công không tồn tại.")
    _validate_deadline(db, paper, payload.deadline)
    assignment.deadline = payload.deadline
    assignment.status = payload.status
    _save(db)
    db.refresh(assignment)
    return assignment


@assignment_router.delete(
    "/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_assignment(
    assignment_id: int, db: DbSession, current_user: OrganizerUser
):
    assignment = _get_assignment(db, assignment_id)
    db.delete(assignment)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@review_router.get("", response_model=list[ReviewOutput])
def list_reviews(
    db: DbSession,
    current_user: CurrentUser,
    assignment_id: int | None = None,
):
    query = select(Review).order_by(Review.id)
    if current_user.role == "reviewer":
        query = query.join(
            ReviewAssignment, ReviewAssignment.id == Review.assignment_id
        ).where(ReviewAssignment.reviewer_id == current_user.id)
    elif current_user.role not in ("admin", "organizer"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem đánh giá.")
    if assignment_id is not None:
        query = query.where(Review.assignment_id == assignment_id)
    return db.scalars(query).all()


@review_router.post(
    "",
    response_model=ReviewOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    payload: ReviewInput, db: DbSession, current_user: ReviewerUser
):
    assignment = _get_assignment(db, payload.assignment_id)
    if current_user.role != "reviewer" or assignment.reviewer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân công phản biện.")
    if db.get(Review, assignment.id) is not None:
        raise HTTPException(status_code=409, detail="Phân công này đã có đánh giá.")
    now = datetime.now(UTC).replace(tzinfo=None)
    if assignment.deadline <= now:
        raise HTTPException(status_code=422, detail="Đã quá hạn gửi đánh giá.")
    if assignment.status not in ("assigned", "in_progress"):
        raise HTTPException(status_code=409, detail="Phân công không còn ở trạng thái nhận đánh giá.")

    review = Review(**payload.model_dump())
    assignment.status = "completed"
    db.add(review)
    _save(db, conflict_message="Phân công này đã có đánh giá.")
    db.refresh(review)
    return review


@review_router.put("/{review_id}", response_model=ReviewOutput)
def update_review(
    review_id: int, payload: ReviewUpdate, db: DbSession, current_user: ReviewerUser
):
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá.")
    assignment = _get_assignment(db, review.assignment_id)
    if current_user.role != "reviewer" or assignment.reviewer_id != current_user.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá.")
    if assignment.deadline <= datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(status_code=422, detail="Đã quá hạn chỉnh sửa đánh giá.")
    review.comments = payload.comments
    review.recommendation = payload.recommendation
    review.score = payload.score
    review.submitted_at = datetime.now(UTC)
    _save(db)
    db.refresh(review)
    return review
