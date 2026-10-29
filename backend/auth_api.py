from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import User
from security import CurrentUser, SessionLocal, create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["Xác thực"])


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: str


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_db():
    with SessionLocal() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=TokenOutput)
def login(payload: LoginInput, db: DbSession):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOutput(access_token=create_access_token(user))


@router.get("/me", response_model=UserOutput)
def read_current_user(current_user: CurrentUser):
    return current_user
