from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.jwt_tokens import create_access_token
from backend.models.user import User
from backend.repositories.refresh_token_repository import (
    create_refresh_token,
    get_refresh_token_by_hash,
    revoke_refresh_token,
)
from backend.repositories.user_repository import create_user, get_user_by_email
from backend.security import (
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from sqlalchemy.ext.asyncio import AsyncSession


class UserAlreadyExistsError(Exception):
    pass


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    existing_user = await get_user_by_email(session, email)
    if existing_user is not None:
        raise UserAlreadyExistsError(f"User with email {email} already exists")

    hashed_password = hash_password(password)
    return await create_user(session, email=email, hashed_password=hashed_password)


class InvalidCredentialsError(Exception):
    pass


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, email)

    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid email or password")

    return user


async def _issue_tokens(session: AsyncSession, user_id: int) -> tuple[str, str]:
    access_token = create_access_token(user_id)

    raw_refresh_token = generate_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    await create_refresh_token(
        session,
        user_id=user_id,
        token_hash=hash_token(raw_refresh_token),
        expires_at=expires_at,
    )

    return access_token, raw_refresh_token


async def login_user(
    session: AsyncSession, email: str, password: str
) -> tuple[str, str]:
    user = await authenticate_user(session, email, password)
    return await _issue_tokens(session, user.id)


class InvalidRefreshTokenError(Exception):
    pass


async def refresh_tokens(
    session: AsyncSession, raw_refresh_token: str
) -> tuple[str, str]:
    token_hash = hash_token(raw_refresh_token)
    stored = await get_refresh_token_by_hash(session, token_hash)

    if stored is None:
        raise InvalidRefreshTokenError("Refresh token is not defind")

    if stored.revoked:
        raise InvalidRefreshTokenError("Refresh token was revoked")

    if stored.expires_at < datetime.now(timezone.utc):
        raise InvalidRefreshTokenError("expires_at is expired")

    await revoke_refresh_token(session, stored)

    return await _issue_tokens(session, stored.user_id)


async def logout_user(session: AsyncSession, raw_refresh_token: str) -> None:
    token_hash = hash_token(raw_refresh_token)
    stored = await get_refresh_token_by_hash(session, token_hash)

    if stored is not None and not stored.revoked:
        await revoke_refresh_token(session, stored)
