import hashlib
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import URL, create_engine, event, select
from sqlalchemy.orm import Session

from database import DATABASE_PATH
from models import (
    Base,
    Conference,
    Notification,
    Paper,
    PaperAuthor,
    Registration,
    Review,
    ReviewAssignment,
    ReviewerProfile,
    PresentationSession,
    User,
)


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def create_database():
    engine = create_engine(URL.create("sqlite", database=str(DATABASE_PATH)))

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def seed_sample_data(engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as db, db.begin():
      
        users_by_email = {
            "organizer@example.com": ("Nguyen Minh Anh", "organizer"),
            "author@example.com": ("Tran Bao Linh", "author"),
            "reviewer@example.com": ("Le Quang Huy", "reviewer"),
        }

        admin_email = os.getenv("DEMO_ADMIN_EMAIL", "admin@example.com")
        admin_password = os.getenv("DEMO_ADMIN_PASSWORD")

        if admin_password:
            users_by_email[admin_email] = ("Quan tri vien", "admin")


        users = {}
        for email, (name, role) in users_by_email.items():
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    full_name=name,
                    email=email,
                    password_hash=_hash_password(
    admin_password if role == "admin" else "sample-password"
),
                    role=role,
                )
                db.add(user)
                db.flush()
            users[email] = user

        conference = db.scalar(
            select(Conference).where(
                Conference.title == "Hội nghị Khoa học Công nghệ 2027"
            )
        )
        if conference is None:
            conference = Conference(
                title="Hội nghị Khoa học Công nghệ 2027",
                description="Hội nghị khoa học mẫu.",
                venue="Hà Nội",
                starts_at=now + timedelta(days=90),
                ends_at=now + timedelta(days=92),
                submission_deadline=now + timedelta(days=30),
                review_deadline=now + timedelta(days=60),
                registration_deadline=now + timedelta(days=80),
                created_by=users["organizer@example.com"].id,
            )
            db.add(conference)
            db.flush()

        presentation = db.scalar(
            select(PresentationSession).where(
                PresentationSession.conference_id == conference.id,
                PresentationSession.title == "Trí tuệ nhân tạo",
            )
        )
        if presentation is None:
            presentation = PresentationSession(
                conference_id=conference.id,
                title="Trí tuệ nhân tạo",
                room="Phòng A",
                starts_at=conference.starts_at + timedelta(hours=1),
                ends_at=conference.starts_at + timedelta(hours=2),
            )
            db.add(presentation)
            db.flush()

        paper = db.scalar(
            select(Paper).where(
                Paper.conference_id == conference.id,
                Paper.title == "Ứng dụng học máy trong phân tích dữ liệu",
            )
        )
        if paper is None:
            paper = Paper(
                conference_id=conference.id,
                submitted_by=users["author@example.com"].id,
                session_id=presentation.id,
                title="Ứng dụng học máy trong phân tích dữ liệu",
                abstract="Nghiên cứu minh họa về ứng dụng các phương pháp học máy.",
                keywords="học máy, phân tích dữ liệu",
                status="submitted",
                submitted_at=now,
            )
            db.add(paper)
            db.flush()

        author = db.get(PaperAuthor, (paper.id, users["author@example.com"].id))
        if author is None:
            db.add(
                PaperAuthor(
                    paper_id=paper.id,
                    user_id=users["author@example.com"].id,
                    author_order=1,
                    is_corresponding=True,
                )
            )

        reviewer = users["reviewer@example.com"]
        if db.get(ReviewerProfile, reviewer.id) is None:
            db.add(
                ReviewerProfile(
                    user_id=reviewer.id,
                    expertise="Trí tuệ nhân tạo, học máy",
                )
            )

        assignment = db.scalar(
            select(ReviewAssignment).where(
                ReviewAssignment.paper_id == paper.id,
                ReviewAssignment.reviewer_id == reviewer.id,
            )
        )
        if assignment is None:
            assignment = ReviewAssignment(
                paper_id=paper.id,
                reviewer_id=reviewer.id,
                assigned_by=users["organizer@example.com"].id,
                deadline=conference.review_deadline,
                status="completed",
            )
            db.add(assignment)
            db.flush()

        if db.scalar(
            select(Review).where(Review.assignment_id == assignment.id)
        ) is None:
            db.add(
                Review(
                    assignment_id=assignment.id,
                    comments="Bài báo có hướng tiếp cận phù hợp với chủ đề hội nghị.",
                    recommendation="minor_revision",
                    score=4,
                )
            )

        author_user = users["author@example.com"]
        if db.scalar(
            select(Registration).where(
                Registration.conference_id == conference.id,
                Registration.user_id == author_user.id,
            )
        ) is None:
            db.add(
                Registration(
                    conference_id=conference.id,
                    user_id=author_user.id,
                    status="registered",
                )
            )

        if db.scalar(
            select(Notification).where(
                Notification.user_id == author_user.id,
                Notification.title == "Xác nhận nhận bài báo",
            )
        ) is None:
            db.add(
                Notification(
                    user_id=author_user.id,
                    title="Xác nhận nhận bài báo",
                    message="Bài báo mẫu đã được ghi nhận.",
                    email_draft="Kính gửi tác giả, bài báo của bạn đã được ghi nhận.",
                )
            )


def main() -> None:
    engine = create_database()
    seed_sample_data(engine)
    print(f"Database and sample data initialized at: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
