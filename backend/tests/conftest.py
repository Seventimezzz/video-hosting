from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from backend.database import async_session_factory
from backend.repositories.user_repository import get_user_by_email


@pytest.fixture
async def unique_email() -> AsyncGenerator[str, None]:
    email = f"user-{uuid4()}@example.com"
    yield email

    async with async_session_factory() as session:
        user = await get_user_by_email(session, email)
        if user is not None:
            await session.delete(user)
            await session.commit()
