from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from db.models import User
from db.session import get_db, init_db


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    nickname: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    nickname: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def auth_database(db: Session = Depends(get_db)) -> Session:
    try:
        init_db()
        return db
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="DB 연결이 필요합니다. Postgres 실행 후 DATABASE_URL을 확인해주세요.",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 없습니다.",
        )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )

    try:
        init_db()
        user = db.get(User, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="DB 연결이 필요합니다. Postgres 실행 후 DATABASE_URL을 확인해주세요.",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
        )

    return user


@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(request: SignupRequest, db: Session = Depends(auth_database)) -> UserResponse:
    existing = db.scalars(select(User).where(User.email == request.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다.")

    user = User(
        email=request.email,
        nickname=request.nickname,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_response(user)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(auth_database)) -> TokenResponse:
    user = db.scalars(select(User).where(User.email == request.email)).first()
    if user is None or user.password_hash is None:
        raise HTTPException(
            status_code=401,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return user_response(current_user)


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, nickname=user.nickname)
