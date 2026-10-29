from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from author_api import router as author_router
from auth_api import router as auth_router
from ai_api import router as ai_router
from conference_api import router as conference_router
from paper_api import router as paper_router
from registration_api import router as registration_router
from review_api import assignment_router, review_router
from reviewer_api import router as reviewer_router
from session_api import router as session_router
from statistics_api import router as statistics_router

app = FastAPI(title="Hệ thống quản lý hội nghị khoa học có tích hợp AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(conference_router)
app.include_router(paper_router)
app.include_router(author_router)
app.include_router(reviewer_router)
app.include_router(assignment_router)
app.include_router(review_router)
app.include_router(session_router)
app.include_router(registration_router)
app.include_router(statistics_router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hệ thống quản lý hội nghị khoa học có tích hợp AI"}


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
