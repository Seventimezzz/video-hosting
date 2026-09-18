import shutil
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from backend.config import settings
from backend.database import async_session_factory
from backend.models.refresh_token import RefreshToken
from backend.models.video import Video
from backend.models.video_upload import VideoUpload
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


@pytest.fixture(autouse=True)
def _clean_upload_tmp_dir():
    yield
    shutil.rmtree(settings.upload_tmp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
async def _clean_videos(unique_email):
    # unique_email сам не чистит videos/video_uploads (FK без CASCADE,
    # известный баг — обсудим отдельно), поэтому чистим здесь, иначе
    # unique_email упадёт на DELETE FROM users с ForeignKeyViolationError.
    yield

    async with async_session_factory() as session:
        user = await get_user_by_email(session, unique_email)
        if user is not None:
            video_ids = (
                (await session.execute(select(Video.id).where(Video.owner_id == user.id)))
                .scalars()
                .all()
            )
            if video_ids:
                await session.execute(
                    delete(VideoUpload).where(VideoUpload.video_id.in_(video_ids))
                )
                await session.execute(delete(Video).where(Video.id.in_(video_ids)))
                await session.commit()


async def register_and_login(client: AsyncClient, email: str, password: str = "mypassword"):
    await client.post("/register", json={"email": email, "password": password})
    await client.post("/login", json={"email": email, "password": password})


async def create_video(client: AsyncClient, title: str = "my video") -> int:
    response = await client.post(
        "/videos", json={"title": title, "description": "test upload"}
    )
    return response.json()["id"]
