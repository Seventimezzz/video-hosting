import asyncio
import shutil
from math import ceil

from backend.config import settings
from backend.models.user import User
from backend.models.video import Video, VideoStatus
from backend.repositories.video_repository import create_video as create_video_in_db
from backend.repositories.video_repository import get_video_by_id, set_video_status
from backend.repositories.video_upload_repository import (
    add_video_upload,
    get_video_upload_by_video_id,
)
from backend.storage import s3_client
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


def _check_video_valid(
    video_id: int, user_id: int, video: Video | None, expected_video_status: VideoStatus
):

    if video is None:
        raise VideoNotFoundError(f"Video with id {video_id} not found")

    if video.owner_id != user_id:
        raise VideoNotBelongThisUserError("Video does not belong to this user")

    if video.status is not expected_video_status:
        raise UploadAlreadyStartedError(
            f"Video with id {video_id} must be {expected_video_status}"
        )


async def start_video_upload(
    session: AsyncSession, video_id: int, user_id: int, total_size: int
):
    video = await get_video_by_id(session, video_id)

    _check_video_valid(video_id, user_id, video, VideoStatus.PENDING)

    storage_path = f"videos/{video_id}/original.mp4"
    add_video_upload(session, video_id, total_size, storage_path)
    set_video_status(video, VideoStatus.UPLOADING)

    await session.commit()
    await session.refresh(video)

    return video


async def upload_video(
    session: AsyncSession,
    video_id: int,
    user_id: int,
    chunk_number: int,
    content: bytes,
):
    video = await get_video_by_id(session, video_id)

    _check_video_valid(video_id, user_id, video, VideoStatus.UPLOADING)

    chunk_dir = settings.upload_tmp_dir / str(video_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    final_path = chunk_dir / f"chunk_{chunk_number:06d}"
    if final_path.exists():
        return video

    tmp_path = chunk_dir / f"chunk_{chunk_number:06d}.part"
    tmp_path.write_bytes(content)
    tmp_path.rename(final_path)

    return video


class ChunksMissingError(Exception):
    pass


class ChunksSizeMismatchError(Exception):
    pass


class StorageUploadError(Exception):
    pass


async def upload_video_complete(video_id: int, user_id: int, session: AsyncSession):
    video_upload = await get_video_upload_by_video_id(session, video_id)
    video = await get_video_by_id(session, video_id)

    _check_video_valid(video_id, user_id, video, VideoStatus.UPLOADING)

    chunk_dir = settings.upload_tmp_dir / str(video_id)

    chunk_paths = sorted(chunk_dir.glob("chunk_" + "[0-9]" * 6))

    expected_chunk_count = ceil(
        video_upload.total_size / settings.upload_chunk_size_bytes
    )
    chunk_numbers = [int(p.name.removeprefix("chunk_")) for p in chunk_paths]

    if chunk_numbers != list(range(1, expected_chunk_count + 1)):
        raise ChunksMissingError(
            f"Video with id {video_id} expected {expected_chunk_count} chunks, "
            f"got {chunk_numbers}"
        )

    total_received = sum(p.stat().st_size for p in chunk_paths)
    if total_received != video_upload.total_size:
        raise ChunksSizeMismatchError(
            f"Video with id {video_id} expected {video_upload.total_size} bytes, "
            f"got {total_received}"
        )

    assembled_path = chunk_dir / "assembled.mp4"
    with assembled_path.open("wb") as assembled_file:
        for chunk_path in chunk_paths:
            assembled_file.write(chunk_path.read_bytes())

    try:
        await asyncio.to_thread(
            s3_client.upload_file,
            str(assembled_path),
            settings.minio_bucket,
            video_upload.storage_path,
        )
    except Exception as e:
        raise StorageUploadError(f"Failed to upload video {video_id} to storage") from e

    shutil.rmtree(chunk_dir)

    set_video_status(video, VideoStatus.UPLOADED)
    await session.commit()
    await session.refresh(video)

    return video
