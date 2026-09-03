from backend.database import get_db
from backend.services.auth_service import UserAlreadyExistsError, register_user
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str


@router.post("/register", response_model=UserResponse)
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_db)):
    try:
        user = await register_user(session, email=data.email, password=data.password)
    except UserAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Email already registered")
    return user
