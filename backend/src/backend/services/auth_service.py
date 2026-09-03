from backend.models.user import User
from backend.repositories.user_repository import create_user, get_user_by_email
from backend.security import hash_password
from sqlalchemy.ext.asyncio import AsyncSession


class UserAlreadyExistsError(Exception):
    pass


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    existing_user = await get_user_by_email(session, email)
    if existing_user is not None:
        raise UserAlreadyExistsError(f"User with email {email} already exists")

    hashed_password = hash_password(password)
    return await create_user(session, email=email, hashed_password=hashed_password)
