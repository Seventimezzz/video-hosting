from backend.models.video import Video, VideoStatus
from backend.models.video_upload import VideoUpload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_video_by_id(session: AsyncSession, video_id: int) -> Video | None:
    result = await session.execute(select(Video).where(Video.id == video_id))
    return result.scalar_one_or_none()


async def create_video(
    session: AsyncSession, title: str, description: str, owner_id: int
) -> Video:
    video = Video(title=title, description=description, owner_id=owner_id)
    session.add(video)
    await session.commit()
    await session.refresh(video)
    return video


def set_video_status(video: Video, status: VideoStatus) -> Video:
    video.status = status
    return video


def add_video_upload(
    session: AsyncSession, video_id: int, total_size: int, storage_path: str
) -> VideoUpload:
    video_upload = VideoUpload(
        video_id=video_id, total_size=total_size, storage_path=storage_path
    )
    session.add(video_upload)
    return video_upload
