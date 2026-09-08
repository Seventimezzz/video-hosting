from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import delete

from backend.database import async_session_factory
from backend.models.refresh_token import RefreshToken
from backend.repositories.user_repository import get_user_by_email


@pytest.fixture
async def unique_email() -> AsyncGenerator[str, None]:
    email = f"user-{uuid4()}@example.com"
    yield email

    async with async_session_factory() as session:
        user = await get_user_by_email(session, email)
        if user is not None:
            await session.execute(
                delete(RefreshToken).where(RefreshToken.user_id == user.id)
            )
            await session.delete(user)
            await session.commit()
