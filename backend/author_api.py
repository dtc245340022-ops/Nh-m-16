from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import URL, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import Paper, PaperAuthor, ReviewAssignment, User
from security import CurrentUser

router = APIRouter(prefix="/api/papers", tags=["Tác giả"])

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


class AuthorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    author_order: int | None = Field(default=None, gt=0)
    is_corresponding: bool = False


class AuthorOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    full_name: str
    email: str
    author_order: int
    is_corresponding: bool


def _get_paper(db: Session, paper_id: int) -> Paper:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài báo.")
    return paper


def _can_manage_paper(db: Session, paper: Paper, user: User) -> bool:
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


def _require_access(db: Session, paper: Paper, user: User) -> None:
    if not _can_manage_paper(db, paper, user):
        raise HTTPException(status_code=404, detail="Không tìm thấy bài báo.")


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tác giả đã được liên kết hoặc thứ tự tác giả không hợp lệ.",
        ) from error


@router.get("/{paper_id}/authors", response_model=list[AuthorOutput])
def list_paper_authors(paper_id: int, db: DbSession, current_user: CurrentUser):
    paper = _get_paper(db, paper_id)
    _require_access(db, paper, current_user)
    rows = db.execute(
        select(
            User.id.label("user_id"),
            User.full_name,
            User.email,
            PaperAuthor.author_order,
            PaperAuthor.is_corresponding,
        )
        .join(PaperAuthor, PaperAuthor.user_id == User.id)
        .where(PaperAuthor.paper_id == paper_id)
        .order_by(PaperAuthor.author_order)
    ).mappings()
    return [AuthorOutput.model_validate(row) for row in rows]


@router.post(
    "/{paper_id}/authors",
    response_model=AuthorOutput,
    status_code=status.HTTP_201_CREATED,
)
def add_paper_author(
    paper_id: int, payload: AuthorInput, db: DbSession, current_user: CurrentUser
):
    paper = _get_paper(db, paper_id)
    if current_user.role not in ("admin", "organizer", "author"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền sửa danh sách tác giả.")
    _require_access(db, paper, current_user)
    if current_user.role == "author" and payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Chỉ có thể liên kết tài khoản của chính bạn.")
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=422, detail="Tác giả không tồn tại.")
    if db.get(PaperAuthor, (paper_id, payload.user_id)) is not None:
        raise HTTPException(status_code=422, detail="Tác giả đã được thêm vào bài báo.")

    next_order = db.scalar(
        select(func.coalesce(func.max(PaperAuthor.author_order), 0)).where(
            PaperAuthor.paper_id == paper_id
        )
    ) + 1
    author_order = payload.author_order or next_order
    if payload.is_corresponding:
        db.query(PaperAuthor).filter(
            PaperAuthor.paper_id == paper_id
        ).update({PaperAuthor.is_corresponding: False})

    author = PaperAuthor(
        paper_id=paper_id,
        user_id=payload.user_id,
        author_order=author_order,
        is_corresponding=payload.is_corresponding,
    )
    db.add(author)
    _save(db)
    user = db.get(User, payload.user_id)
    return AuthorOutput(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        author_order=author.author_order,
        is_corresponding=author.is_corresponding,
    )


@router.delete(
    "/{paper_id}/authors/{author_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_paper_author(
    paper_id: int, author_id: int, db: DbSession, current_user: CurrentUser
):
    paper = _get_paper(db, paper_id)
    if current_user.role not in ("admin", "organizer", "author"):
        raise HTTPException(status_code=403, detail="Bạn không có quyền sửa danh sách tác giả.")
    _require_access(db, paper, current_user)
    if current_user.role == "author" and author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Chỉ có thể gỡ tài khoản của chính bạn.")
    author = db.get(PaperAuthor, (paper_id, author_id))
    if author is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác giả của bài báo.")
    db.delete(author)
    _save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
