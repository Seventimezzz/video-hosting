from backend.models.user import User
from backend.models.video import VideoStatus
from backend.repositories.video_repository import create_video as create_video_in_db
from backend.repositories.video_repository import get_video_by_id, set_video_status
from backend.repositories.video_upload_repository import add_video_upload
from sqlalchemy.ext.asyncio import AsyncSession


async def create_video(title: str, description: str, session: AsyncSession, user: User):
    video = await create_video_in_db(session, title, description, user.id)
    return video


class VideoNotFoundError(Exception):
    pass


class UploadAlreadyStartedError(Exception):
    pass


class VideoNotBelongThisUserError(Exception):
    pass


async def start_video_upload(
    session: AsyncSession, video_id: int, user_id: int, total_size: int
):
    video = await get_video_by_id(session, video_id)

    if video is None:
        raise VideoNotFoundError(f"Video with id {video_id} not found")

    if video.owner_id != user_id:
        raise VideoNotBelongThisUserError("Video does not belong to this user")

    if video.status is not VideoStatus.PENDING:
        raise UploadAlreadyStartedError(
            f"Video with id {video_id} already started upload"
        )

    storage_path = f"videos/{video_id}/original.mp4"
    add_video_upload(session, video_id, total_size, storage_path)
    set_video_status(video, VideoStatus.UPLOADING)

    await session.commit()
    await session.refresh(video)

    return video
