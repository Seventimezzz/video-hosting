import datetime

from backend.models.refresh_token import RefreshToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def create_refresh_token(
    session: AsyncSession, user_id: int, token_hash: str, expires_at: datetime
) -> RefreshToken:
    refresh_token = RefreshToken(
        user_id=user_id, token_hash=token_hash, expires_at=expires_at
    )
    session.add(refresh_token)
    await session.commit()
    await session.refresh(refresh_token)
    return refresh_token


async def get_refresh_token_by_hash(
    session: AsyncSession, token_hash: str
) -> RefreshToken | None:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(
    session: AsyncSession, refresh_token: RefreshToken
) -> None:
    refresh_token.revoked = True
    await session.commit()
