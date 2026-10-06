import asyncio
import subprocess
import tempfile
from pathlib import Path

from backend.config import settings
from backend.database import async_session_factory
from backend.models.video import VideoStatus
from backend.repositories.video_repository import get_video_by_id, set_video_status
from backend.repositories.video_upload_repository import get_video_upload_by_video_id
from backend.storage import s3_client


def transcode_video(video_id: int) -> None:
    asyncio.run(_transcode_video_async(video_id))


class TranscodeError(Exception):
    pass


async def _transcode_video_async(video_id: int) -> None:
    async with async_session_factory() as session:
        video = await get_video_by_id(session, video_id)
        video_upload = await get_video_upload_by_video_id(session, video_id)

        set_video_status(video, VideoStatus.PROCESSING)

        await session.commit()

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                original_path = tmp_path / "original.mp4"

                await asyncio.to_thread(
                    s3_client.download_file,
                    settings.minio_bucket,
                    video_upload.storage_path,
                    str(original_path),
                )

                hls_dir = tmp_path / "hls"

                hls_dir.mkdir()

                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "ffmpeg",
                        "-i",
                        str(original_path),
                        "-c:v",
                        "libx264",
                        "-c:a",
                        "aac",
                        "-hls_time",
                        "4",
                        "-hls_playlist_type",
                        "vod",
                        "-hls_segment_filename",
                        str(hls_dir / "segment_%03d.ts"),
                        str(hls_dir / "playlist.m3u8"),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    raise TranscodeError(result.stderr)

                for file_path in hls_dir.rglob("*"):
                    if not file_path.is_file():
                        continue

                    relative_path = file_path.relative_to(hls_dir)
                    s3_key = f"videos/{video_id}/hls/{relative_path.as_posix()}"

                    await asyncio.to_thread(
                        s3_client.upload_file,
                        str(file_path),
                        settings.minio_bucket,
                        s3_key,
                    )
        except Exception:
            set_video_status(video, VideoStatus.FAILED)
            await session.commit()
            raise
        else:
            set_video_status(video, VideoStatus.READY)
            await session.commit()


def ping_task(x: int) -> int:
    print(f"ping_task {x}")
    return x * 2
