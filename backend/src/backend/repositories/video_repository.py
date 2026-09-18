from backend.models.video import Video, VideoStatus
from backend.models.video_upload import VideoUpload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def delete_video(
    session: AsyncSession, video: Video, video_upload: VideoUpload | None
) -> None:
    if video_upload is not None:
        await session.delete(video_upload)
        await session.flush()

    await session.delete(video)
    await session.commit()


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


async def get_all_video(session: AsyncSession) -> list[Video]:
    result = await session.execute(select(Video))
    return list(result.scalars().all())
