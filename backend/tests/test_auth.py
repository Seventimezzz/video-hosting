from httpx import ASGITransport, AsyncClient

from backend import app


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
