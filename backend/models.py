from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'organizer', 'author', 'reviewer')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )


class Conference(Base):
    __tablename__ = "conferences"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_conferences_date_range"),
        CheckConstraint(
            "submission_deadline < starts_at", name="ck_conferences_submission_deadline"
        ),
        CheckConstraint(
            "review_deadline < starts_at", name="ck_conferences_review_deadline"
        ),
        CheckConstraint(
            "registration_deadline < starts_at",
            name="ck_conferences_registration_deadline",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    venue: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submission_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class PresentationSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_sessions_date_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conference_id: Mapped[int] = mapped_column(
        ForeignKey("conferences.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    room: Mapped[str | None] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'submitted', 'under_review', 'accepted', 'rejected')",
            name="ck_papers_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conference_id: Mapped[int] = mapped_column(
        ForeignKey("conferences.id", ondelete="CASCADE"), nullable=False
    )
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)


class PaperAuthor(Base):
    __tablename__ = "paper_authors"
    __table_args__ = (
        UniqueConstraint("paper_id", "author_order", name="uq_paper_author_order"),
        CheckConstraint("author_order > 0", name="ck_paper_author_order"),
    )

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    author_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_corresponding: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class ReviewerProfile(Base):
    __tablename__ = "reviewer_profiles"
    __table_args__ = (
        CheckConstraint("max_assignments > 0", name="ck_reviewer_max_assignments"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    expertise: Mapped[str] = mapped_column(Text, nullable=False)
    max_assignments: Mapped[int] = mapped_column(Integer, default=5, nullable=False)


class ReviewAssignment(Base):
    __tablename__ = "review_assignments"
    __table_args__ = (
        UniqueConstraint("paper_id", "reviewer_id", name="uq_review_assignment"),
        CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed', 'declined')",
            name="ck_review_assignments_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "recommendation IN ('accept', 'minor_revision', 'major_revision', 'reject')",
            name="ck_reviews_recommendation",
        ),
        CheckConstraint(
            "score >= 1 AND score <= 5", name="ck_reviews_score"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("review_assignments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    comments: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("conference_id", "user_id", name="uq_registration"),
        CheckConstraint(
            "status IN ('registered', 'cancelled', 'attended')",
            name="ck_registrations_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conference_id: Mapped[int] = mapped_column(
        ForeignKey("conferences.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="registered", nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "title", name="uq_notification_user_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    email_draft: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
