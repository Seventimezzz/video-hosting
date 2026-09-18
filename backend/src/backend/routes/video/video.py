from datetime import datetime

from backend.config import settings
from backend.database import get_db
from backend.dependencies.auth import get_current_user
from backend.models.user import User
from backend.models.video import VideoStatus
from backend.repositories.video_repository import get_all_video
from backend.services.video_service import (
    ChunksMissingError,
    ChunksSizeMismatchError,
    StorageUploadError,
    UploadAlreadyStartedError,
    VideoNotBelongThisUserError,
    VideoNotFoundError,
    create_video,
    start_video_upload,
    upload_video,
    upload_video_complete,
    video_by_id,
)
from backend.services.video_service import (
    delete_video as delete_video_service,
)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.delete("/videos/{id}")
async def delete_video(
    id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        await delete_video_service(session, id, user.id)
    except VideoNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    except VideoNotBelongThisUserError:
        raise HTTPException(
            status_code=403, detail="Video does not belong to this user"
        )


@router.get("/videos/{id}")
async def video(id: int, session: AsyncSession = Depends(get_db)):
    try:
        video = await video_by_id(session, id)
    except VideoNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/videos")
async def all_video(session: AsyncSession = Depends(get_db)):
    videos = await get_all_video(session)
    return videos


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


class StartUploadResponse(BaseModel):
    id: int
    title: str
    description: str
    status: VideoStatus
    created_at: datetime
    chunk_size: int


@router.post("/videos/{video_id}/upload", response_model=StartUploadResponse)
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
        raise HTTPException(
            status_code=403, detail="Video does not belong to this user"
        )
    except UploadAlreadyStartedError:
        raise HTTPException(status_code=409, detail="Video already registered")
    return StartUploadResponse(
        id=video.id,
        title=video.title,
        description=video.description,
        status=video.status,
        created_at=video.created_at,
        chunk_size=settings.upload_chunk_size_bytes,
    )


@router.put("/videos/{video_id}/upload/chunks/{chunk_number}")
async def upload_chunk(
    video_id: int,
    chunk_number: int,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    content = await request.body()
    try:
        video = await upload_video(session, video_id, user.id, chunk_number, content)
    except VideoNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    except VideoNotBelongThisUserError:
        raise HTTPException(
            status_code=403, detail="Video does not belong to this user"
        )
    except UploadAlreadyStartedError:
        raise HTTPException(status_code=409, detail="Video already registered")
    return video


@router.post("/videos/{video_id}/upload/complete")
async def upload_complete(
    video_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        video = await upload_video_complete(video_id, user.id, session)
    except VideoNotFoundError:
        raise HTTPException(status_code=404, detail="Video not found")
    except VideoNotBelongThisUserError:
        raise HTTPException(
            status_code=403, detail="Video does not belong to this user"
        )
    except UploadAlreadyStartedError:
        raise HTTPException(status_code=409, detail="Video already registered")
    except ChunksMissingError:
        raise HTTPException(status_code=409, detail="Not all chunks were uploaded")
    except ChunksSizeMismatchError:
        raise HTTPException(
            status_code=409, detail="Uploaded chunks do not match expected total size"
        )
    except StorageUploadError:
        raise HTTPException(status_code=502, detail="Failed to upload video to storage")
    return video
