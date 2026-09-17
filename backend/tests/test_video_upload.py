import shutil
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from backend import app
from backend.config import settings
from backend.database import async_session_factory
from backend.models.video import Video
from backend.models.video_upload import VideoUpload
from backend.repositories.user_repository import get_user_by_email


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


@pytest.fixture
def mock_s3_upload():
    with patch("backend.services.video_service.s3_client") as mock_client:
        yield mock_client.upload_file


@pytest.fixture(autouse=True)
def _small_chunk_size(monkeypatch):
    # Протокол ожидает, что все чанки, кроме последнего, имеют ровно
    # settings.upload_chunk_size_bytes байт (иначе upload_video_complete
    # неверно посчитает expected_chunk_count). Уменьшаем размер чанка на
    # время теста, чтобы не гонять по 5 МБ в каждом тесте.
    monkeypatch.setattr(settings, "upload_chunk_size_bytes", 10)


async def _register_and_login(client: AsyncClient, email: str, password: str = "mypassword"):
    await client.post("/register", json={"email": email, "password": password})
    await client.post("/login", json={"email": email, "password": password})


async def _create_video(client: AsyncClient, title: str = "my video") -> int:
    response = await client.post(
        "/videos", json={"title": title, "description": "test upload"}
    )
    return response.json()["id"]


async def _start_upload(client: AsyncClient, video_id: int, total_size: int):
    return await client.post(
        f"/videos/{video_id}/upload", json={"total_size": total_size}
    )


async def _upload_chunk(client: AsyncClient, video_id: int, chunk_number: int, content: bytes):
    return await client.put(
        f"/videos/{video_id}/upload/chunks/{chunk_number}", content=content
    )


async def _complete_upload(client: AsyncClient, video_id: int):
    return await client.post(f"/videos/{video_id}/upload/complete")


async def test_full_upload_flow_success(unique_email, mock_s3_upload):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client)

        chunk_a = b"a" * 10
        chunk_b = b"b" * 5
        total_size = len(chunk_a) + len(chunk_b)

        start_response = await _start_upload(client, video_id, total_size)
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "uploading"

        chunk1_response = await _upload_chunk(client, video_id, 1, chunk_a)
        assert chunk1_response.status_code == 200

        chunk2_response = await _upload_chunk(client, video_id, 2, chunk_b)
        assert chunk2_response.status_code == 200

        complete_response = await _complete_upload(client, video_id)

    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "uploaded"
    mock_s3_upload.assert_called_once()
    assert mock_s3_upload.call_args.args[1] == settings.minio_bucket
    assert mock_s3_upload.call_args.args[2] == f"videos/{video_id}/original.mp4"


async def test_upload_chunk_twice_is_idempotent(unique_email, mock_s3_upload):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client)

        chunk = b"a" * 10
        await _start_upload(client, video_id, len(chunk))

        first_response = await _upload_chunk(client, video_id, 1, chunk)
        assert first_response.status_code == 200

        # Повторная отправка того же чанка (например, из-за обрыва связи и
        # ретрая клиента) не должна падать и не должна портить уже
        # сохранённые данные.
        second_response = await _upload_chunk(client, video_id, 1, chunk)
        assert second_response.status_code == 200

        complete_response = await _complete_upload(client, video_id)

    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "uploaded"


async def test_complete_upload_fails_when_chunk_missing(unique_email, mock_s3_upload):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client)

        chunk_a = b"a" * 10
        chunk_b = b"b" * 10
        total_size = len(chunk_a) + len(chunk_b)

        await _start_upload(client, video_id, total_size)
        # Загружаем только первый чанк из двух ожидаемых — второй "потерялся".
        await _upload_chunk(client, video_id, 1, chunk_a)

        complete_response = await _complete_upload(client, video_id)

    assert complete_response.status_code == 409
    mock_s3_upload.assert_not_called()


async def test_upload_chunk_without_starting_upload_fails(unique_email, mock_s3_upload):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client)

        response = await _upload_chunk(client, video_id, 1, b"data")

    assert response.status_code == 409


async def test_start_upload_twice_fails(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client)

        first = await _start_upload(client, video_id, 100)
        assert first.status_code == 200

        second = await _start_upload(client, video_id, 100)

    assert second.status_code == 409


async def test_upload_chunk_for_nonexistent_video(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)

        response = await _upload_chunk(client, 999_999, 1, b"data")

    assert response.status_code == 404


async def test_upload_chunk_for_video_of_another_user(unique_email):
    other_email = f"other-{unique_email}"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as owner_client:
        await _register_and_login(owner_client, unique_email)
        video_id = await _create_video(owner_client)
        await _start_upload(owner_client, video_id, 100)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as other_client:
        await _register_and_login(other_client, other_email)
        response = await _upload_chunk(other_client, video_id, 1, b"data")

    assert response.status_code == 403


async def test_complete_upload_reports_storage_failure(unique_email, mock_s3_upload):
    mock_s3_upload.side_effect = Exception("boom")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client)

        chunk = b"a" * 10
        await _start_upload(client, video_id, len(chunk))
        await _upload_chunk(client, video_id, 1, chunk)

        response = await _complete_upload(client, video_id)

    assert response.status_code == 502
