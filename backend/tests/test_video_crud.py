from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend import app
from conftest import create_video as _create_video
from conftest import register_and_login as _register_and_login


async def test_list_videos_is_public_and_includes_other_users_videos(unique_email):
    other_email = f"other-{unique_email}"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as owner_client:
        await _register_and_login(owner_client, unique_email)
        video_id = await _create_video(owner_client, title="owner's video")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as other_client:
        await _register_and_login(other_client, other_email)
        # list видео доступен без токена вообще
        response = await other_client.get("/videos")

    assert response.status_code == 200
    video_ids = [video["id"] for video in response.json()]
    assert video_id in video_ids


async def test_list_videos_without_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/videos")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_video_by_id_success(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)
        video_id = await _create_video(client, title="my video")

        response = await client.get(f"/videos/{video_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == video_id
    assert body["title"] == "my video"


async def test_get_video_by_id_without_auth(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as owner_client:
        await _register_and_login(owner_client, unique_email)
        video_id = await _create_video(owner_client)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon_client:
        # get одного видео тоже публичный — без токена вообще
        response = await anon_client.get(f"/videos/{video_id}")

    assert response.status_code == 200
    assert response.json()["id"] == video_id


async def test_get_nonexistent_video(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/videos/999999")

    assert response.status_code == 404


async def test_delete_video_success(unique_email):
    with patch("backend.services.video_service.s3_client"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _register_and_login(client, unique_email)
            video_id = await _create_video(client)

            delete_response = await client.delete(f"/videos/{video_id}")
            assert delete_response.status_code == 200

            get_response = await client.get(f"/videos/{video_id}")

    assert get_response.status_code == 404


async def test_delete_video_removes_uploaded_file_from_storage(unique_email):
    with patch("backend.services.video_service.s3_client") as mock_client:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _register_and_login(client, unique_email)
            video_id = await _create_video(client)

            chunk = b"a" * 10
            await client.post(f"/videos/{video_id}/upload", json={"total_size": 10})
            await client.put(f"/videos/{video_id}/upload/chunks/1", content=chunk)
            await client.post(f"/videos/{video_id}/upload/complete")

            delete_response = await client.delete(f"/videos/{video_id}")

    assert delete_response.status_code == 200
    mock_client.delete_object.assert_called_once()
    assert mock_client.delete_object.call_args.kwargs["Key"] == f"videos/{video_id}/original.mp4"


async def test_delete_video_without_upload_does_not_touch_storage(unique_email):
    with patch("backend.services.video_service.s3_client") as mock_client:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _register_and_login(client, unique_email)
            video_id = await _create_video(client)

            delete_response = await client.delete(f"/videos/{video_id}")

    assert delete_response.status_code == 200
    mock_client.delete_object.assert_not_called()


async def test_delete_video_without_auth(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as owner_client:
        await _register_and_login(owner_client, unique_email)
        video_id = await _create_video(owner_client)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon_client:
        response = await anon_client.delete(f"/videos/{video_id}")

    assert response.status_code == 401


async def test_delete_video_of_another_user_fails(unique_email):
    other_email = f"other-{unique_email}"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as owner_client:
        await _register_and_login(owner_client, unique_email)
        video_id = await _create_video(owner_client)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as other_client:
        await _register_and_login(other_client, other_email)
        response = await other_client.delete(f"/videos/{video_id}")

    assert response.status_code == 403


async def test_delete_nonexistent_video(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, unique_email)

        response = await client.delete("/videos/999999")

    assert response.status_code == 404
