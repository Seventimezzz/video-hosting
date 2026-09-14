from backend.models.video_upload import VideoUpload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def add_video_upload(
    session: AsyncSession, video_id: int, total_size: int, storage_path: str
) -> VideoUpload:
    video_upload = VideoUpload(
        video_id=video_id, total_size=total_size, storage_path=storage_path
    )
    session.add(video_upload)
    return video_upload


async def get_video_upload_by_video_id(
    session: AsyncSession, video_id: int
) -> VideoUpload | None:
    result = await session.execute(
        select(VideoUpload).where(VideoUpload.video_id == video_id)
    )
    return result.scalar_one_or_none()
