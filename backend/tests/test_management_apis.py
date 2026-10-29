import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters"
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import auth_api
import conference_api
import paper_api
import author_api
import registration_api
import review_api
import reviewer_api
import security
import session_api
import statistics_api
from main import app
from models import (
    Base,
    Conference,
    Paper,
    PaperAuthor,
    Registration,
    Review,
    ReviewAssignment,
    ReviewerProfile,
    User,
)


class ManagementApiTests(unittest.TestCase):
    def setUp(self):
        database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        database_file.close()
        self.database_path = Path(database_file.name)
        self.engine = create_engine(
            URL.create("sqlite", database=str(self.database_path))
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._seed_database()

        for module in (
            auth_api,
            conference_api,
            paper_api,
            author_api,
            reviewer_api,
            review_api,
            session_api,
            registration_api,
            statistics_api,
        ):
            module.SessionLocal = self.session_factory
        security.SessionLocal = self.session_factory
        self.client = TestClient(app)
        self.tokens = {
            "organizer": self._token(1),
            "author": self._token(2),
            "other_author": self._token(3),
            "reviewer": self._token(4),
            "other_reviewer": self._token(5),
        }
        self.headers = {
            role: {"Authorization": f"Bearer {token}"}
            for role, token in self.tokens.items()
        }

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.database_path.unlink(missing_ok=True)

    def _seed_database(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        starts_at = now + timedelta(days=100)
        self.starts_at = starts_at
        self.ends_at = starts_at + timedelta(days=2)
        self.review_deadline = now + timedelta(days=70)
        with Session(self.engine) as db, db.begin():
            db.add_all(
                [
                    User(
                        id=1,
                        full_name="Organizer",
                        email="organizer@test.com",
                        password_hash="unused",
                        role="organizer",
                    ),
                    User(
                        id=2,
                        full_name="Author One",
                        email="author1@test.com",
                        password_hash="unused",
                        role="author",
                    ),
                    User(
                        id=3,
                        full_name="Author Two",
                        email="author2@test.com",
                        password_hash="unused",
                        role="author",
                    ),
                    User(
                        id=4,
                        full_name="Reviewer One",
                        email="reviewer1@test.com",
                        password_hash="unused",
                        role="reviewer",
                    ),
                    User(
                        id=5,
                        full_name="Reviewer Two",
                        email="reviewer2@test.com",
                        password_hash="unused",
                        role="reviewer",
                    ),
                ]
            )
            db.flush()
            db.add(
                Conference(
                    id=1,
                    title="Test conference",
                    description="Conference for isolated API tests",
                    venue="Test venue",
                    starts_at=starts_at,
                    ends_at=self.ends_at,
                    submission_deadline=now + timedelta(days=30),
                    review_deadline=self.review_deadline,
                    registration_deadline=now + timedelta(days=90),
                    created_by=1,
                )
            )
            db.flush()
            db.add_all(
                [
                    Paper(
                        id=1,
                        conference_id=1,
                        submitted_by=2,
                        title="Submitted paper",
                        abstract="Research abstract one.",
                        keywords="artificial intelligence, language",
                        status="submitted",
                    ),
                    Paper(
                        id=2,
                        conference_id=1,
                        submitted_by=3,
                        title="Accepted paper",
                        abstract="Research abstract two.",
                        keywords="systems",
                        status="accepted",
                    ),
                    Paper(
                        id=3,
                        conference_id=1,
                        submitted_by=2,
                        title="Rejected paper",
                        abstract="Research abstract three.",
                        keywords="data",
                        status="rejected",
                    ),
                    ReviewerProfile(
                        user_id=4,
                        expertise="Artificial intelligence, NLP",
                        max_assignments=3,
                    ),
                    ReviewerProfile(
                        user_id=5,
                        expertise="Systems",
                        max_assignments=2,
                    ),
                    Registration(
                        id=1,
                        conference_id=1,
                        user_id=2,
                        status="registered",
                    ),
                ]
            )
            db.flush()
            db.add_all(
                [
                    PaperAuthor(
                        paper_id=1,
                        user_id=2,
                        author_order=1,
                        is_corresponding=True,
                    ),
                    ReviewAssignment(
                        id=1,
                        paper_id=1,
                        reviewer_id=4,
                        assigned_by=1,
                        deadline=now + timedelta(days=40),
                        status="completed",
                    ),
                    ReviewAssignment(
                        id=2,
                        paper_id=2,
                        reviewer_id=5,
                        assigned_by=1,
                        deadline=now - timedelta(days=1),
                        status="assigned",
                    ),
                ]
            )
            db.flush()
            db.add(
                Review(
                    id=1,
                    assignment_id=1,
                    comments="Existing review",
                    recommendation="accept",
                    score=4,
                )
            )

    def _token(self, user_id):
        with Session(self.engine) as db:
            return security.create_access_token(db.get(User, user_id))

    def _conference_payload(self, title="New test conference"):
        start = self.starts_at + timedelta(days=10)
        return {
            "title": title,
            "description": "Conference description",
            "venue": "Room 1",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(days=2)).isoformat(),
            "submission_deadline": (start - timedelta(days=60)).isoformat(),
            "review_deadline": (start - timedelta(days=30)).isoformat(),
            "registration_deadline": (start - timedelta(days=5)).isoformat(),
        }

    def _paper_payload(self, title="New test paper", conference_id=1):
        return {
            "conference_id": conference_id,
            "title": title,
            "abstract": "A test abstract with sufficient content.",
            "keywords": "testing, science",
        }

    def _assignment_payload(self, paper_id=3, reviewer_id=4):
        return {
            "paper_id": paper_id,
            "reviewer_id": reviewer_id,
            "deadline": (datetime.now(UTC) + timedelta(days=20)).isoformat(),
        }

    def _session_payload(self, title="Test presentation"):
        start = self.starts_at + timedelta(hours=4)
        return {
            "conference_id": 1,
            "title": title,
            "room": "Room B",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
        }

    def test_conference_crud_and_validation(self):
        created = self.client.post(
            "/api/conferences",
            json=self._conference_payload(),
            headers=self.headers["organizer"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        conference_id = created.json()["id"]
        self.assertEqual(created.json()["created_by"], 1)

        listed = self.client.get("/api/conferences", headers=self.headers["author"])
        self.assertEqual(listed.status_code, 200)
        self.assertIn(conference_id, [item["id"] for item in listed.json()])
        fetched = self.client.get(
            f"/api/conferences/{conference_id}", headers=self.headers["author"]
        )
        self.assertEqual(fetched.status_code, 200)

        update_data = self._conference_payload("Updated conference")
        updated = self.client.put(
            f"/api/conferences/{conference_id}",
            json=update_data,
            headers=self.headers["organizer"],
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["title"], "Updated conference")
        self.assertEqual(
            self.client.delete(
                f"/api/conferences/{conference_id}",
                headers=self.headers["organizer"],
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.get(
                f"/api/conferences/{conference_id}",
                headers=self.headers["author"],
            ).status_code,
            404,
        )
        invalid = self._conference_payload()
        invalid["ends_at"] = invalid["starts_at"]
        self.assertEqual(
            self.client.post(
                "/api/conferences",
                json=invalid,
                headers=self.headers["organizer"],
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/conferences",
                json=self._conference_payload(),
                headers=self.headers["author"],
            ).status_code,
            403,
        )

    def test_paper_crud_search_and_reference_validation(self):
        created = self.client.post(
            "/api/papers",
            json=self._paper_payload(),
            headers=self.headers["author"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        paper_id = created.json()["id"]
        self.assertEqual(created.json()["submitted_by"], 2)
        self.assertEqual(created.json()["status"], "draft")

        listed = self.client.get(
            "/api/papers?title=test&keyword=science",
            headers=self.headers["author"],
        )
        self.assertIn(paper_id, [item["id"] for item in listed.json()])
        self.assertEqual(
            self.client.get(
                f"/api/papers/{paper_id}", headers=self.headers["author"]
            ).status_code,
            200,
        )
        updated_payload = self._paper_payload("Updated title")
        updated = self.client.put(
            f"/api/papers/{paper_id}",
            json=updated_payload,
            headers=self.headers["author"],
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["title"], "Updated title")

        self.assertEqual(
            self.client.delete(
                f"/api/papers/{paper_id}", headers=self.headers["author"]
            ).status_code,
            204,
        )
        invalid = self._paper_payload(conference_id=999)
        self.assertEqual(
            self.client.post(
                "/api/papers", json=invalid, headers=self.headers["author"]
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/papers",
                json={**self._paper_payload(), "status": "accepted"},
                headers=self.headers["author"],
            ).status_code,
            422,
        )

    def test_paper_author_link_management(self):
        added = self.client.post(
            "/api/papers/1/authors",
            json={"user_id": 3, "author_order": 2, "is_corresponding": False},
            headers=self.headers["organizer"],
        )
        self.assertEqual(added.status_code, 201, added.text)
        self.assertEqual(added.json()["user_id"], 3)
        authors = self.client.get(
            "/api/papers/1/authors", headers=self.headers["author"]
        )
        self.assertEqual(
            [item["user_id"] for item in authors.json()], [2, 3]
        )
        self.assertEqual(
            self.client.post(
                "/api/papers/1/authors",
                json={"user_id": 3, "author_order": 2},
                headers=self.headers["organizer"],
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.delete(
                "/api/papers/1/authors/3", headers=self.headers["organizer"]
            ).status_code,
            204,
        )

    def test_assignment_create_update_delete_and_conflicts(self):
        created = self.client.post(
            "/api/review-assignments",
            json=self._assignment_payload(),
            headers=self.headers["organizer"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        assignment_id = created.json()["id"]
        self.assertEqual(created.json()["assigned_by"], 1)

        duplicate = self.client.post(
            "/api/review-assignments",
            json=self._assignment_payload(),
            headers=self.headers["organizer"],
        )
        self.assertEqual(duplicate.status_code, 409)

        updated_payload = {
            "deadline": (datetime.now(UTC) + timedelta(days=25)).isoformat(),
            "status": "in_progress",
        }
        updated = self.client.put(
            f"/api/review-assignments/{assignment_id}",
            json=updated_payload,
            headers=self.headers["organizer"],
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["status"], "in_progress")
        self.assertEqual(
            self.client.delete(
                f"/api/review-assignments/{assignment_id}",
                headers=self.headers["organizer"],
            ).status_code,
            204,
        )

    def test_assignment_prevents_self_review_and_limit_excess(self):
        with Session(self.engine) as db, db.begin():
            db.add(
                Paper(
                    id=4,
                    conference_id=1,
                    submitted_by=4,
                    title="Reviewer-authored paper",
                    abstract="Paper submitted by a reviewer.",
                    status="submitted",
                )
            )
        self.assertEqual(
            self.client.post(
                "/api/review-assignments",
                json=self._assignment_payload(paper_id=4, reviewer_id=4),
                headers=self.headers["organizer"],
            ).status_code,
            409,
        )

        with Session(self.engine) as db, db.begin():
            profile = db.get(ReviewerProfile, 5)
            profile.max_assignments = 1
        self.assertEqual(
            self.client.post(
                "/api/review-assignments",
                json=self._assignment_payload(paper_id=3, reviewer_id=5),
                headers=self.headers["organizer"],
            ).status_code,
            409,
        )

    def test_reviewer_creates_and_updates_own_review(self):
        assignment = self.client.post(
            "/api/review-assignments",
            json=self._assignment_payload(paper_id=3, reviewer_id=4),
            headers=self.headers["organizer"],
        )
        self.assertEqual(assignment.status_code, 201, assignment.text)
        assignment_id = assignment.json()["id"]
        review_body = {
            "assignment_id": assignment_id,
            "comments": "Clear methodology and useful evaluation.",
            "recommendation": "minor_revision",
            "score": 4,
        }
        created = self.client.post(
            "/api/reviews",
            json=review_body,
            headers=self.headers["reviewer"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        review_id = created.json()["id"]
        self.assertEqual(created.json()["assignment_id"], assignment_id)

        updated = self.client.put(
            f"/api/reviews/{review_id}",
            json={
                "comments": "Updated review comments.",
                "recommendation": "accept",
                "score": 5,
            },
            headers=self.headers["reviewer"],
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["score"], 5)
        self.assertEqual(updated.json()["recommendation"], "accept")
        self.assertEqual(
            self.client.get(
                "/api/reviews", headers=self.headers["organizer"]
            ).status_code,
            200,
        )

    def test_review_validation_and_ownership(self):
        other_reviewer_update = self.client.put(
            "/api/reviews/1",
            json={
                "comments": "Unauthorized edit",
                "recommendation": "reject",
                "score": 1,
            },
            headers=self.headers["other_reviewer"],
        )
        self.assertEqual(other_reviewer_update.status_code, 404)

        invalid_score = self.client.post(
            "/api/reviews",
            json={
                "assignment_id": 1,
                "comments": "Invalid score.",
                "recommendation": "accept",
                "score": 7,
            },
            headers=self.headers["reviewer"],
        )
        self.assertEqual(invalid_score.status_code, 422)

        duplicate_review = self.client.post(
            "/api/reviews",
            json={
                "assignment_id": 1,
                "comments": "Duplicate review.",
                "recommendation": "accept",
                "score": 4,
            },
            headers=self.headers["reviewer"],
        )
        self.assertEqual(duplicate_review.status_code, 409)

    def test_session_crud_and_time_conflict_validation(self):
        created = self.client.post(
            "/api/sessions",
            json=self._session_payload(),
            headers=self.headers["organizer"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        session_id = created.json()["id"]
        fetched = self.client.get(
            f"/api/sessions/{session_id}", headers=self.headers["author"]
        )
        self.assertEqual(fetched.status_code, 200)

        update_payload = self._session_payload("Updated session")
        updated = self.client.put(
            f"/api/sessions/{session_id}",
            json=update_payload,
            headers=self.headers["organizer"],
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["title"], "Updated session")

        conflict = self.client.post(
            "/api/sessions",
            json=self._session_payload("Conflicting session"),
            headers=self.headers["organizer"],
        )
        self.assertEqual(conflict.status_code, 409)
        invalid = self._session_payload("Out of conference")
        invalid["starts_at"] = (self.ends_at + timedelta(hours=1)).isoformat()
        invalid["ends_at"] = (self.ends_at + timedelta(hours=2)).isoformat()
        self.assertEqual(
            self.client.post(
                "/api/sessions",
                json=invalid,
                headers=self.headers["organizer"],
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.delete(
                f"/api/sessions/{session_id}",
                headers=self.headers["organizer"],
            ).status_code,
            204,
        )

    def test_registration_create_update_delete_and_duplicate(self):
        duplicate = self.client.post(
            "/api/registrations",
            json={"conference_id": 1, "status": "registered"},
            headers=self.headers["author"],
        )
        self.assertEqual(duplicate.status_code, 409)

        with Session(self.engine) as db, db.begin():
            db.add(
                Conference(
                    id=2,
                    title="Second conference",
                    starts_at=self.starts_at + timedelta(days=20),
                    ends_at=self.ends_at + timedelta(days=20),
                    submission_deadline=self.starts_at + timedelta(days=5),
                    review_deadline=self.starts_at + timedelta(days=10),
                    registration_deadline=self.starts_at + timedelta(days=15),
                    created_by=1,
                )
            )
        created = self.client.post(
            "/api/registrations",
            json={"conference_id": 2, "status": "registered"},
            headers=self.headers["author"],
        )
        self.assertEqual(created.status_code, 201, created.text)
        registration_id = created.json()["id"]
        self.assertEqual(created.json()["user_id"], 2)

        updated = self.client.put(
            f"/api/registrations/{registration_id}",
            json={"conference_id": 2, "status": "cancelled"},
            headers=self.headers["author"],
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["status"], "cancelled")
        self.assertEqual(
            self.client.delete(
                f"/api/registrations/{registration_id}",
                headers=self.headers["author"],
            ).status_code,
            204,
        )

    def test_registration_deadline_and_author_cannot_mark_attendance(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        starts_at = now + timedelta(days=10)
        with Session(self.engine) as db, db.begin():
            db.add(
                Conference(
                    id=2,
                    title="Registration closed conference",
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(days=1),
                    submission_deadline=now - timedelta(days=3),
                    review_deadline=now - timedelta(days=2),
                    registration_deadline=now - timedelta(days=1),
                    created_by=1,
                )
            )
        expired = self.client.post(
            "/api/registrations",
            json={"conference_id": 2, "status": "registered"},
            headers=self.headers["author"],
        )
        self.assertEqual(expired.status_code, 422)
        self.assertEqual(
            self.client.put(
                "/api/registrations/1",
                json={"conference_id": 1, "status": "attended"},
                headers=self.headers["author"],
            ).status_code,
            403,
        )

    def test_statistics_counts_and_organizer_access(self):
        response = self.client.get(
            "/api/statistics", headers=self.headers["organizer"]
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {
                "conferences": 1,
                "papers": 3,
                "reviewers": 2,
                "registrations": 1,
                "accepted_papers": 1,
                "rejected_papers": 1,
                "overdue_reviews": 1,
            },
        )
        self.assertEqual(
            self.client.get(
                "/api/statistics", headers=self.headers["author"]
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
