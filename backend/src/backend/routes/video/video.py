from datetime import datetime

from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models.user import User
from backend.models.video import VideoStatus
from backend.services.video_service import (
    UploadAlreadyStartedError,
    VideoNotBelongThisUserError,
    VideoNotFoundError,
    create_video,
    start_video_upload,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class CreateVideoRequest(BaseModel):
    title: str
    description: str


class CreateVideoResponse(BaseModel):
    id: int
    title: str
    description: str
    status: VideoStatus
    created_at: datetime


@router.post("/videos", response_model=CreateVideoResponse)
async def create(
    data: CreateVideoRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):

    video = await create_video(data.title, data.description, session, user)
    return video


class StartUploadRequest(BaseModel):
    total_size: int


@router.post("/videos/{video_id}/upload")
async def start_upload(
    video_id: int,
    data: StartUploadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        video = await start_video_upload(session, video_id, user.id, data.total_size)
    except VideoNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    except VideoNotBelongThisUserError:
        raise HTTPException(status_code=403, detail="Video does not belong to this user")
    except UploadAlreadyStartedError:
        raise HTTPException(status_code=409, detail="Video already registered")
    return video
