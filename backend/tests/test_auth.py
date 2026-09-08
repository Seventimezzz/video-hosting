from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from backend import app
from backend.config import settings
from backend.models.user import UserRole


async def _register(client: AsyncClient, email: str, password: str = "mypassword"):
    return await client.post("/register", json={"email": email, "password": password})


async def test_register_success(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/register", json={"email": unique_email, "password": "mypassword"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == unique_email
    assert "id" in body


async def test_register_duplicate_email(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/register", json={"email": unique_email, "password": "mypassword"}
        )
        assert first.status_code == 200

        second = await client.post(
            "/register", json={"email": unique_email, "password": "anotherpassword"}
        )

    assert second.status_code == 409
    assert second.json() == {"detail": "Email already registered"}


async def test_register_invalid_email():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/register", json={"email": "not-an-email", "password": "mypassword"}
        )

    assert response.status_code == 422


async def test_login_success(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client, unique_email)

        response = await client.post(
            "/login", json={"email": unique_email, "password": "mypassword"}
        )

    assert response.status_code == 200
    assert response.json() == {"detail": "logged in"}
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_login_wrong_password(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client, unique_email)

        response = await client.post(
            "/login", json={"email": unique_email, "password": "wrongpassword"}
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert "access_token" not in response.cookies


async def test_login_unknown_email(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/login", json={"email": unique_email, "password": "mypassword"}
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


async def test_me_with_valid_token(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client, unique_email)
        await client.post(
            "/login", json={"email": unique_email, "password": "mypassword"}
        )

        response = await client.get("/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == unique_email


async def test_me_without_token():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_me_with_garbage_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": "not-a-real-token"},
    ) as client:
        response = await client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


async def test_me_with_expired_token(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        register_response = await _register(client, unique_email)
        user_id = register_response.json()["id"]

        # create_access_token всегда ставит exp в будущем, поэтому здесь
        # собираем токен вручную с истёкшим временем по той же схеме.
        payload = {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "access",
        }
        expired_token = jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        client.cookies.set("access_token", expired_token)
        response = await client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


async def test_refresh_success(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client, unique_email)
        await client.post(
            "/login", json={"email": unique_email, "password": "mypassword"}
        )
        old_refresh_token = client.cookies.get("refresh_token")

        response = await client.post("/refresh")

    assert response.status_code == 200
    assert response.json() == {"detail": "refreshed"}
    assert "access_token" in response.cookies
    # refresh-токен — случайные байты (secrets.token_urlsafe), поэтому он
    # гарантированно новый. Access-токен при быстром повторном вызове в
    # пределах той же секунды может совпасть: его payload — это только
    # sub/exp/type, а exp считается с точностью до секунды.
    assert response.cookies["refresh_token"] != old_refresh_token


async def test_refresh_without_token():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/refresh")

    assert response.status_code == 401
    assert response.json() == {"detail": "Refresh token is missing"}


async def test_refresh_with_invalid_token():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"refresh_token": "not-a-real-refresh-token"},
    ) as client:
        response = await client.post("/refresh")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


async def test_refresh_reuse_of_old_token_fails(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client, unique_email)
        await client.post(
            "/login", json={"email": unique_email, "password": "mypassword"}
        )
        old_refresh_token = client.cookies.get("refresh_token")

        first_refresh = await client.post("/refresh")
        assert first_refresh.status_code == 200

        client.cookies.set("refresh_token", old_refresh_token)
        second_refresh = await client.post("/refresh")

    assert second_refresh.status_code == 401
    assert second_refresh.json() == {"detail": "Invalid refresh token"}


async def test_logout_clears_cookies_and_revokes_refresh_token(unique_email):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register(client, unique_email)
        await client.post(
            "/login", json={"email": unique_email, "password": "mypassword"}
        )

        logout_response = await client.post("/logout")
        assert logout_response.status_code == 200
        assert logout_response.json() == {"detail": "logged out"}

        # После логаута refresh с тем же (уже отозванным) токеном не должен работать.
        second_refresh = await client.post("/refresh")

    assert "access_token" not in client.cookies
    assert "refresh_token" not in client.cookies
    assert second_refresh.status_code == 401


async def test_logout_without_refresh_token_is_noop():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/logout")

    assert response.status_code == 200
    assert response.json() == {"detail": "logged out"}


@pytest.fixture
def make_user():
    def _make_user(user_id: int, role: UserRole) -> "FakeUser":
        return FakeUser(id=user_id, role=role)

    return _make_user


class FakeUser:
    def __init__(self, id: int, role: UserRole):
        self.id = id
        self.role = role


async def test_require_role_allows_matching_role(make_user):
    from backend.dependencies.auth import require_role

    checker = require_role(UserRole.ADMIN)
    admin = make_user(1, UserRole.ADMIN)

    result = await checker(user=admin)

    assert result is admin


async def test_require_role_rejects_other_role(make_user):
    from fastapi import HTTPException

    from backend.dependencies.auth import require_role

    checker = require_role(UserRole.ADMIN)
    viewer = make_user(1, UserRole.VIEWER)

    with pytest.raises(HTTPException) as exc_info:
        await checker(user=viewer)

    assert exc_info.value.status_code == 403
