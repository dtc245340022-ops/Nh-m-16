from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import URL, create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import (
    Conference,
    Paper,
    PaperAuthor,
    PresentationSession,
    ReviewAssignment,
    User,
)
from security import CurrentUser, require_roles

router = APIRouter(prefix="/api/papers", tags=["Bài báo"])

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


PaperStatus = Literal["draft", "submitted", "under_review", "accepted", "rejected"]


class PaperInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conference_id: int = Field(gt=0)
    session_id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=300)
    abstract: str = Field(min_length=1)
    keywords: str | None = None

    @field_validator("title", "abstract")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be empty")
        return value


class PaperOutput(PaperInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submitted_by: int
    status: PaperStatus


DbSession = Annotated[Session, Depends(get_db)]


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Dữ liệu không hợp lệ hoặc khóa ngoại không tồn tại.",
        ) from error


def _validate_references(db: Session, payload: PaperInput) -> None:
    if db.get(Conference, payload.conference_id) is None:
        raise HTTPException(status_code=422, detail="Hội nghị không tồn tại.")
    if payload.session_id is not None:
        presentation = db.get(PresentationSession, payload.session_id)
        if presentation is None or presentation.conference_id != payload.conference_id:
            raise HTTPException(
                status_code=422,
                detail="Phiên trình bày không tồn tại hoặc không thuộc hội nghị đã chọn.",
            )


def _get_paper(db: Session, paper_id: int) -> Paper:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài báo.")
    return paper


def _can_access_paper(db: Session, paper: Paper, user: User) -> bool:
    if user.role in ("admin", "organizer"):
        return True
    if user.role == "author":
        return paper.submitted_by == user.id or db.get(
            PaperAuthor, (paper.id, user.id)
        ) is not None
    if user.role == "reviewer":
        return db.scalar(
            select(ReviewAssignment.id).where(
                ReviewAssignment.paper_id == paper.id,
                ReviewAssignment.reviewer_id == user.id,
            )
        ) is not None
    return False


def _require_paper_access(db: Session, paper: Paper, user: User) -> None:
    if not _can_access_paper(db, paper, user):
        raise HTTPException(status_code=404, detail="Không tìm thấy bài báo.")


@router.get("", response_model=list[PaperOutput])
def list_papers(
    db: DbSession,
    current_user: CurrentUser,
    title: str | None = Query(default=None, min_length=1),
    keyword: str | None = Query(default=None, min_length=1),
    paper_status: PaperStatus | None = Query(default=None, alias="status"),
):
    query = select(Paper).order_by(Paper.id)
    if title is not None:
        query = query.where(Paper.title.ilike(f"%{title.strip()}%"))
    if keyword is not None:
        query = query.where(Paper.keywords.ilike(f"%{keyword.strip()}%"))
    if paper_status is not None:
        query = query.where(Paper.status == paper_status)
    if current_user.role == "author":
        query = query.where(
            (Paper.submitted_by == current_user.id)
            | (
                Paper.id.in_(
                    select(PaperAuthor.paper_id).where(
                        PaperAuthor.user_id == current_user.id
                    )
                )
            )
        )
    elif current_user.role == "reviewer":
        query = query.where(
            Paper.id.in_(
                select(ReviewAssignment.paper_id).where(
                    ReviewAssignment.reviewer_id == current_user.id
                )
            )
        )
    return db.scalars(query).all()


@router.get("/{paper_id}", response_model=PaperOutput)
def get_paper(paper_id: int, db: DbSession, current_user: CurrentUser):
    paper = _get_paper(db, paper_id)
    _require_paper_access(db, paper, current_user)
    return paper


@router.post("", response_model=PaperOutput, status_code=status.HTTP_201_CREATED)
def create_paper(
    payload: PaperInput,
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles("author"))],
):
    _validate_references(db, payload)
    paper = Paper(
        **payload.model_dump(), submitted_by=current_user.id, status="draft"
    )
    db.add(paper)
    _save(db)
    db.refresh(paper)
    return paper


@router.put("/{paper_id}", response_model=PaperOutput)
def update_paper(
    paper_id: int,
    payload: PaperInput,
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles("author"))],
):
    paper = _get_paper(db, paper_id)
    if current_user.role != "admin" and not _can_access_paper(db, paper, current_user):
        raise HTTPException(status_code=404, detail="Không tìm thấy bài báo.")
    _validate_references(db, payload)
    for field, value in payload.model_dump().items():
        setattr(paper, field, value)
    _save(db)
    db.refresh(paper)
    return paper


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(
    paper_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles("author"))],
):
    paper = _get_paper(db, paper_id)
    if current_user.role != "admin" and not _can_access_paper(db, paper, current_user):
        raise HTTPException(status_code=404, detail="Không tìm thấy bài báo.")
    db.delete(paper)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
