from backend.config import settings
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models.user import User
from backend.services.auth_service import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserAlreadyExistsError,
    login_user,
    logout_user,
    refresh_tokens,
    register_user,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.refresh_token_expire_days * 86400,
    )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str


@router.post("/register", response_model=UserResponse)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_db)):
    try:
        user = await register_user(session, email=data.email, password=data.password)
    except UserAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Email already registered")
    return user


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(
    data: LoginRequest, response: Response, session: AsyncSession = Depends(get_db)
):
    try:
        access_token, refresh_token = await login_user(
            session, data.email, data.password
        )
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _set_auth_cookies(response, access_token, refresh_token)
    return {"detail": "logged in"}


@router.post("/refresh")
async def refresh(
    request: Request, response: Response, session: AsyncSession = Depends(get_db)
):
    raw_refresh_token = request.cookies.get("refresh_token")

    if raw_refresh_token is None:
        raise HTTPException(status_code=401, detail="Refresh token is missing")

    try:
        access_token, refresh_token = await refresh_tokens(session, raw_refresh_token)
    except InvalidRefreshTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    _set_auth_cookies(response, access_token, refresh_token)
    return {"detail": "refreshed"}


@router.post("/logout")
async def logout(
    request: Request, response: Response, session: AsyncSession = Depends(get_db)
):
    raw_refresh_token = request.cookies.get("refresh_token")

    if raw_refresh_token is not None:
        await logout_user(session, raw_refresh_token)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"detail": "logged out"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user
