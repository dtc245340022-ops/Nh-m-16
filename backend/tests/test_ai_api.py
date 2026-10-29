import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-characters"
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from google.genai import errors
import httpx
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import ai_api
import security
from main import app
from models import (
    Base,
    Conference,
    Paper,
    PaperAuthor,
    ReviewerProfile,
    ReviewAssignment,
    User,
)


class AiSummaryApiTests(unittest.TestCase):
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
        ai_api.SessionLocal = self.session_factory
        security.SessionLocal = self.session_factory
        self.client = TestClient(app)
        self.tokens = {
            "organizer": self._token(1, "organizer"),
            "owner": self._token(2, "author"),
            "other_author": self._token(3, "author"),
            "assigned_reviewer": self._token(4, "reviewer"),
            "other_reviewer": self._token(5, "reviewer"),
        }

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
                        id=1,
                        full_name="Organizer",
                        email="organizer@test.com",
                        password_hash="unused",
                        role="organizer",
                    ),
                    User(
                        id=2,
                        full_name="Paper Owner",
                        email="owner@test.com",
                        password_hash="unused",
                        role="author",
                    ),
                    User(
                        id=3,
                        full_name="Other Author",
                        email="other-author@test.com",
                        password_hash="unused",
                        role="author",
                    ),
                    User(
                        id=4,
                        full_name="Assigned Reviewer",
                        email="assigned@test.com",
                        password_hash="unused",
                        role="reviewer",
                    ),
                    User(
                        id=5,
                        full_name="Other Reviewer",
                        email="other-reviewer@test.com",
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
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(days=2),
                    submission_deadline=now + timedelta(days=30),
                    review_deadline=now + timedelta(days=60),
                    registration_deadline=now + timedelta(days=80),
                    created_by=1,
                )
            )
            db.flush()
            db.add(
                Paper(
                    id=1,
                    conference_id=1,
                    submitted_by=2,
                    title="A grounded research title",
                    abstract="This paper studies a small sample and reports its measured results.",
                    keywords="research, sample",
                    status="submitted",
                )
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
                        deadline=now + timedelta(days=20),
                        status="assigned",
                    ),
                    ReviewerProfile(user_id=4, expertise="machine learning"),
                    ReviewerProfile(user_id=5, expertise="data mining, statistics"),
                ]
            )

    def _token(self, user_id, role):
        with Session(self.engine) as db:
            return security.create_access_token(db.get(User, user_id))

    def _headers(self, account):
        return {"Authorization": f"Bearer {self.tokens[account]}"}

    def test_summary_uses_mocked_gemini_and_returns_fixed_warning(self):
        response_body = {
            "summary": "Bài báo nghiên cứu một mẫu nhỏ và báo cáo kết quả đo được.",
            "key_points": ["Nghiên cứu sử dụng một mẫu nhỏ."],
            "important_keywords": ["nghiên cứu", "mẫu"],
        }
        fake_client = Mock()
        fake_client.models.generate_content.return_value.text = json.dumps(
            response_body, ensure_ascii=False
        )

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "mock-api-key"}),
            patch.object(ai_api, "_create_gemini_client", return_value=fake_client),
        ):
            response = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("owner")
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["summary"], response_body["summary"])
        self.assertEqual(response.json()["key_points"], response_body["key_points"])
        self.assertEqual(
            response.json()["important_keywords"], response_body["important_keywords"]
        )
        self.assertIn("có thể sai", response.json()["warning"])
        request = fake_client.models.generate_content.call_args.kwargs
        self.assertIn("A grounded research title", request["contents"])
        self.assertIn("small sample", request["contents"])
        self.assertIn("TÓM TẮT GỐC", request["contents"])
        self.assertIn("bằng tiếng Việt", request["contents"])
        self.assertNotIn("API key", request["contents"])

    def test_missing_api_key_is_explicit_and_never_calls_gemini(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(ai_api, "_create_gemini_client") as create_client,
        ):
            response = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("owner")
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["detail"])
        create_client.assert_not_called()

    def test_access_requires_ownership_or_assignment(self):
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "mock-api-key"}),
            patch.object(
                ai_api,
                "_create_gemini_client",
                return_value=self._fake_client(),
            ) as create_client,
        ):
            organizer_response = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("organizer")
            )
            reviewer_response = self.client.post(
                "/api/ai/summarize-paper/1",
                headers=self._headers("assigned_reviewer"),
            )
            non_owner_response = self.client.post(
                "/api/ai/summarize-paper/1",
                headers=self._headers("other_author"),
            )
            unassigned_response = self.client.post(
                "/api/ai/summarize-paper/1",
                headers=self._headers("other_reviewer"),
            )

        self.assertEqual(organizer_response.status_code, 200)
        self.assertEqual(reviewer_response.status_code, 200)
        self.assertEqual(non_owner_response.status_code, 404)
        self.assertEqual(unassigned_response.status_code, 404)
        self.assertEqual(create_client.call_count, 2)

    def test_invalid_paper_and_unauthenticated_request(self):
        missing = self.client.post(
            "/api/ai/summarize-paper/99", headers=self._headers("owner")
        )
        unauthenticated = self.client.post("/api/ai/summarize-paper/1")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(unauthenticated.status_code, 401)

    def test_invalid_paper_content_is_rejected_before_provider_call(self):
        with Session(self.engine) as db, db.begin():
            db.get(Paper, 1).abstract = "   "
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "mock-api-key"}),
            patch.object(ai_api, "_create_gemini_client") as create_client,
        ):
            response = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("owner")
            )

        self.assertEqual(response.status_code, 422)
        create_client.assert_not_called()

    def test_rate_limit_and_timeout_do_not_expose_provider_details(self):
        fake_client = Mock()
        fake_client.models.generate_content.side_effect = errors.APIError(
            code=429,
            response_json={"error": {"message": "secret provider detail"}},
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "secret-api-key"}),
            patch.object(ai_api, "_create_gemini_client", return_value=fake_client),
        ):
            limited = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("owner")
            )

        fake_client.models.generate_content.side_effect = httpx.ReadTimeout(
            "secret-api-key"
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "secret-api-key"}),
            patch.object(ai_api, "_create_gemini_client", return_value=fake_client),
        ):
            timed_out = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("owner")
            )

        for response, expected_status in ((limited, 429), (timed_out, 504)):
            self.assertEqual(response.status_code, expected_status)
            self.assertNotIn("secret-api-key", response.text)
            self.assertNotIn("secret provider detail", response.text)

    def test_invalid_gemini_response_is_reported_as_upstream_error(self):
        fake_client = Mock()
        fake_client.models.generate_content.return_value.text = "not-json"
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "mock-api-key"}),
            patch.object(ai_api, "_create_gemini_client", return_value=fake_client),
        ):
            response = self.client.post(
                "/api/ai/summarize-paper/1", headers=self._headers("owner")
            )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("not-json", response.text)

    def test_suggest_reviewers_returns_only_database_candidates(self):
        fake_client = Mock()
        fake_client.models.generate_content.return_value.text = json.dumps(
            {
                "suggestions": [
                    {
                        "reviewer_id": 5,
                        "reason": "Chuyên môn thống kê phù hợp với phương pháp bài báo.",
                    }
                ]
            },
            ensure_ascii=False,
        )
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "mock-api-key"}),
            patch.object(ai_api, "_create_gemini_client", return_value=fake_client),
        ):
            response = self.client.post(
                "/api/ai/suggest-reviewers/1",
                headers=self._headers("organizer"),
            )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["paper_id"], 1)
        self.assertEqual([item["reviewer_id"] for item in body["suggestions"]], [5])
        self.assertEqual(body["suggestions"][0]["full_name"], "Other Reviewer")
        self.assertIn("Chuyên môn thống kê", body["suggestions"][0]["reason"])
        self.assertIn("xung đột lợi ích", body["warning"])
        prompt = fake_client.models.generate_content.call_args.kwargs["contents"]
        self.assertIn('"reviewer_id": 5', prompt)
        self.assertNotIn('"reviewer_id": 2', prompt)
        self.assertNotIn('"reviewer_id": 4', prompt)
        self.assertNotIn("full_name", prompt)
        self.assertNotIn("Other Reviewer", prompt)
        self.assertEqual(
            fake_client.models.generate_content.call_args.kwargs["model"],
            "gemini-flash-lite-latest",
        )

    def test_reviewer_suggestion_requires_organizer_role(self):
        author_response = self.client.post(
            "/api/ai/suggest-reviewers/1",
            headers=self._headers("owner"),
        )
        reviewer_response = self.client.post(
            "/api/ai/suggest-reviewers/1",
            headers=self._headers("assigned_reviewer"),
        )
        self.assertEqual(author_response.status_code, 403)
        self.assertEqual(reviewer_response.status_code, 403)

    def test_gemini_cannot_return_non_candidate_or_duplicate_reviewers(self):
        for suggestions in (
            [{"reviewer_id": 2, "reason": "Author"}],
            [
                {"reviewer_id": 5, "reason": "Relevant"},
                {"reviewer_id": 5, "reason": "Duplicate"},
            ],
        ):
            fake_client = Mock()
            fake_client.models.generate_content.return_value.text = json.dumps(
                {"suggestions": suggestions}
            )
            with (
                patch.dict(os.environ, {"GEMINI_API_KEY": "mock-api-key"}),
                patch.object(
                    ai_api, "_create_gemini_client", return_value=fake_client
                ),
            ):
                response = self.client.post(
                    "/api/ai/suggest-reviewers/1",
                    headers=self._headers("organizer"),
                )
            self.assertEqual(response.status_code, 502)

    def test_no_candidates_returns_empty_without_calling_gemini(self):
        with Session(self.engine) as db, db.begin():
            db.query(ReviewerProfile).delete()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(ai_api, "_create_gemini_client") as create_client,
        ):
            response = self.client.post(
                "/api/ai/suggest-reviewers/1",
                headers=self._headers("organizer"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggestions"], [])
        create_client.assert_not_called()

    def _fake_client(self):
        client = Mock()
        client.models.generate_content.return_value.text = json.dumps(
            {
                "summary": "Tóm tắt kiểm thử.",
                "key_points": ["Một ý chính."],
                "important_keywords": ["kiểm thử"],
            },
            ensure_ascii=False,
        )
        return client


if __name__ == "__main__":
    unittest.main()
