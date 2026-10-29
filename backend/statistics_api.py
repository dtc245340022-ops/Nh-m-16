from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import URL, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from database import DATABASE_PATH
from models import (
    Conference,
    Paper,
    Registration,
    ReviewAssignment,
    ReviewerProfile,
)
from security import OrganizerUser

router = APIRouter(prefix="/api/statistics", tags=["Thống kê"])

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


class StatisticsOutput(BaseModel):
    conferences: int
    papers: int
    reviewers: int
    registrations: int
    accepted_papers: int
    rejected_papers: int
    overdue_reviews: int


def _count(db: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return db.scalar(query) or 0


@router.get("", response_model=StatisticsOutput)
def get_statistics(db: DbSession, current_user: OrganizerUser):
    now = datetime.now(UTC).replace(tzinfo=None)
    return StatisticsOutput(
        conferences=_count(db, Conference),
        papers=_count(db, Paper),
        reviewers=_count(db, ReviewerProfile),
        registrations=_count(db, Registration),
        accepted_papers=_count(db, Paper, Paper.status == "accepted"),
        rejected_papers=_count(db, Paper, Paper.status == "rejected"),
        overdue_reviews=_count(
            db,
            ReviewAssignment,
            ReviewAssignment.deadline < now,
            ReviewAssignment.status.in_(("assigned", "in_progress")),
        ),
    )
