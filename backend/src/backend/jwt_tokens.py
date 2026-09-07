from datetime import datetime, timedelta, timezone

import jwt

from backend.config import settings


class InvalidTokenError(Exception):
    pass


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {"sub": str(user_id), "exp": expire, "type": "access"}

    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    return token


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError("Invalid or expired token") from e

    if payload["type"] != "access":
        raise InvalidTokenError("Not an access token")

    return payload
