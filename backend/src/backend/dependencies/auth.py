from backend.database import get_db
from backend.jwt_tokens import InvalidTokenError, decode_access_token
from backend.models.user import User, UserRole
from backend.repositories.user_repository import get_user_by_id
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_db)
) -> User:
    token = request.cookies.get("access_token")

    if token is None:
        raise HTTPException(401, "Not authenticated")

    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise HTTPException(401, "Invalid or expired token")

    user_id = int(payload["sub"])

    user = await get_user_by_id(session, user_id)

    if user is None:
        raise HTTPException(401, "User is not defind")

    return user


def require_role(required_role: UserRole):
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
            raise HTTPException(403, "Insufficient permissions")
        return user

    return role_checker
