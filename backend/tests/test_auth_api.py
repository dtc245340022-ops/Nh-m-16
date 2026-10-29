import tempfile
import hashlib
import os
import tempfile
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters"
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import author_api
import auth_api
import conference_api
import paper_api
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


class AuthenticationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hashes = {
            password: security.hash_password(password)
            for password in (
                "organizer-password",
                "author-one-password",
                "author-two-password",
                "reviewer-one-password",
                "reviewer-two-password",
            )
        }

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
        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
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

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.database_path.unlink(missing_ok=True)

    def _seed_database(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        starts_at = now + timedelta(days=90)
        with Session(self.engine) as db, db.begin():
            db.add_all(
                [
                    User(
                        full_name="Organizer",
                        email="organizer@test.com",
                        password_hash=self.password_hashes["organizer-password"],
                        role="organizer",
                    ),
                    User(
                        full_name="Author One",
                        email="author1@test.com",
                        password_hash=self.password_hashes["author-one-password"],
                        role="author",
                    ),
                    User(
                        full_name="Author Two",
                        email="author2@test.com",
                        password_hash=self.password_hashes["author-two-password"],
                        role="author",
                    ),
                    User(
                        full_name="Reviewer One",
                        email="reviewer1@test.com",
                        password_hash=self.password_hashes["reviewer-one-password"],
                        role="reviewer",
                    ),
                    User(
                        full_name="Reviewer Two",
                        email="reviewer2@test.com",
                        password_hash=self.password_hashes["reviewer-two-password"],
                        role="reviewer",
                    ),
                ]
            )
            db.flush()
            db.add(
                Conference(
                    title="Test conference",
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(days=2),
                    submission_deadline=now + timedelta(days=30),
                    review_deadline=now + timedelta(days=60),
                    registration_deadline=now + timedelta(days=80),
                    created_by=1,
                )
            )
            db.flush()
            db.add_all(
                [
                    Paper(
                        conference_id=1,
                        submitted_by=2,
                        title="Author One paper",
                        abstract="First abstract",
                        status="submitted",
                    ),
                    Paper(
                        conference_id=1,
                        submitted_by=3,
                        title="Author Two paper",
                        abstract="Second abstract",
                        status="submitted",
                    ),
                    ReviewerProfile(user_id=4, expertise="AI"),
                    ReviewerProfile(user_id=5, expertise="Systems"),
                    Registration(
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
                        paper_id=1,
                        reviewer_id=4,
                        assigned_by=1,
                        deadline=now + timedelta(days=40),
                        status="assigned",
                    ),
                    ReviewAssignment(
                        paper_id=2,
                        reviewer_id=5,
                        assigned_by=1,
                        deadline=now + timedelta(days=40),
                        status="assigned",
                    ),
                ]
            )
            db.flush()
            db.add(
                Review(
                    assignment_id=1,
                    comments="Existing review",
                    recommendation="accept",
                    score=4,
                )
            )

    def _login(self, email, password):
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_login_jwt_and_current_user(self):
        token = self._login("author1@test.com", "author-one-password")
        response = self.client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], 2)
        self.assertNotIn("password_hash", response.json())

        wrong_password = self.client.post(
            "/api/auth/login",
            json={"email": "author1@test.com", "password": "wrong"},
        )
        self.assertEqual(wrong_password.status_code, 401)

        invalid_token = self.client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid.token"}
        )
        self.assertEqual(invalid_token.status_code, 401)

        expired_token = jwt.encode(
            {
                "sub": "2",
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            security.JWT_SECRET_KEY,
            algorithm=security.JWT_ALGORITHM,
        )
        expired = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        self.assertEqual(expired.status_code, 401)

    def test_author_permissions_and_record_ownership(self):
        token = self._login("author1@test.com", "author-one-password")
        headers = {"Authorization": f"Bearer {token}"}

        papers = self.client.get("/api/papers", headers=headers)
        self.assertEqual([paper["id"] for paper in papers.json()], [1])
        self.assertEqual(
            self.client.get("/api/papers/2", headers=headers).status_code, 404
        )
        self.assertEqual(
            self.client.post("/api/conferences", json={}, headers=headers).status_code,
            403,
        )
        forged_organizer = jwt.encode(
            {
                "sub": "2",
                "role": "organizer",
                "exp": datetime.now(UTC) + timedelta(minutes=10),
            },
            security.JWT_SECRET_KEY,
            algorithm=security.JWT_ALGORITHM,
        )
        starts_at = datetime.now(UTC) + timedelta(days=100)
        conference_data = {
            "title": "Must remain forbidden",
            "starts_at": starts_at.isoformat(),
            "ends_at": (starts_at + timedelta(days=2)).isoformat(),
            "submission_deadline": (starts_at - timedelta(days=60)).isoformat(),
            "review_deadline": (starts_at - timedelta(days=30)).isoformat(),
            "registration_deadline": (starts_at - timedelta(days=5)).isoformat(),
        }
        self.assertEqual(
            self.client.post(
                "/api/conferences",
                json=conference_data,
                headers={"Authorization": f"Bearer {forged_organizer}"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                "/api/papers/2",
                json={
                    "conference_id": 1,
                    "title": "Tampered",
                    "abstract": "Tampered",
                },
                headers=headers,
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get("/api/reviewers", headers=headers).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                "/api/review-assignments",
                json={},
                headers=headers,
            ).status_code,
            403,
        )

        create = self.client.post(
            "/api/papers",
            json={
                "conference_id": 1,
                "title": "New paper",
                "abstract": "New abstract",
                "submitted_by": 3,
            },
            headers=headers,
        )
        self.assertEqual(create.status_code, 422)

        created = self.client.post(
            "/api/papers",
            json={
                "conference_id": 1,
                "title": "My new paper",
                "abstract": "My abstract",
            },
            headers=headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["submitted_by"], 2)

        forbidden_status = self.client.post(
            "/api/papers",
            json={
                "conference_id": 1,
                "title": "New paper",
                "abstract": "New abstract",
                "status": "accepted",
            },
            headers=headers,
        )
        self.assertEqual(forbidden_status.status_code, 422)

        registration = self.client.post(
            "/api/registrations",
            json={"conference_id": 1, "status": "registered", "user_id": 3},
            headers=headers,
        )
        self.assertEqual(registration.status_code, 422)

        other_author_token = self._login("author2@test.com", "author-two-password")
        other_headers = {"Authorization": f"Bearer {other_author_token}"}
        self.assertEqual(
            self.client.put(
                "/api/registrations/1",
                json={"conference_id": 1, "status": "cancelled"},
                headers=other_headers,
            ).status_code,
            404,
        )

    def test_reviewer_scoping_and_organizer_permissions(self):
        reviewer_token = self._login(
            "reviewer1@test.com", "reviewer-one-password"
        )
        reviewer_headers = {"Authorization": f"Bearer {reviewer_token}"}
        assignments = self.client.get(
            "/api/review-assignments", headers=reviewer_headers
        )
        self.assertEqual(
            [item["reviewer_id"] for item in assignments.json()], [4]
        )
        self.assertEqual(
            self.client.get("/api/papers/2", headers=reviewer_headers).status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                "/api/reviews/1",
                json={
                    "comments": "Tampered",
                    "recommendation": "reject",
                    "score": 1,
                },
                headers={
                    "Authorization": (
                        "Bearer "
                        + self._login(
                            "reviewer2@test.com", "reviewer-two-password"
                        )
                    )
                },
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/statistics",
                headers={
                    "Authorization": "Bearer "
                    + self._login("author1@test.com", "author-one-password")
                },
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/sessions",
                json={},
                headers={
                    "Authorization": "Bearer "
                    + self._login("author1@test.com", "author-one-password")
                },
            ).status_code,
            403,
        )

        organizer_token = self._login(
            "organizer@test.com", "organizer-password"
        )
        organizer_headers = {"Authorization": f"Bearer {organizer_token}"}
        self.assertEqual(
            self.client.get("/api/statistics", headers=organizer_headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/conferences",
                json={
                    "title": "Organizer conference",
                    "starts_at": (datetime.now(UTC) + timedelta(days=100)).isoformat(),
                    "ends_at": (datetime.now(UTC) + timedelta(days=102)).isoformat(),
                    "submission_deadline": (
                        datetime.now(UTC) + timedelta(days=40)
                    ).isoformat(),
                    "review_deadline": (
                        datetime.now(UTC) + timedelta(days=70)
                    ).isoformat(),
                    "registration_deadline": (
                        datetime.now(UTC) + timedelta(days=90)
                    ).isoformat(),
                },
                headers=organizer_headers,
            ).status_code,
            201,
        )

    def test_sample_password_hashes_remain_compatible(self):
        salt = b"existing-sample-account-salt"
        digest = hashlib.pbkdf2_hmac(
            "sha256", b"sample-password", salt, 310_000
        )
        legacy_hash = f"pbkdf2_sha256${salt.hex()}${digest.hex()}"
        self.assertTrue(security.verify_password("sample-password", legacy_hash))
        self.assertFalse(security.verify_password("wrong-password", legacy_hash))
