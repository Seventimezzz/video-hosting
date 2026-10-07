import asyncio
import subprocess
import tempfile
from pathlib import Path

from backend.config import settings
from backend.database import async_session_factory
from backend.models.video import VideoStatus
from backend.repositories.video_repository import (
    get_video_by_id,
    mark_video_ready,
    set_video_status,
)
from backend.repositories.video_upload_repository import get_video_upload_by_video_id
from backend.storage import s3_client

SEGMENT_SECONDS = 4

RENDITIONS = [
    {
        "name": "1080p",
        "height": 1080,
        "bitrate": "5000k",
        "maxrate": "5350k",
        "bufsize": "7500k",
    },
    {
        "name": "720p",
        "height": 720,
        "bitrate": "2800k",
        "maxrate": "2996k",
        "bufsize": "4200k",
    },
    {
        "name": "480p",
        "height": 480,
        "bitrate": "1400k",
        "maxrate": "1498k",
        "bufsize": "2100k",
    },
]


def transcode_video(video_id: int) -> None:
    asyncio.run(_transcode_video_async(video_id))


class TranscodeError(Exception):
    pass


def _build_ffmpeg_command(input_path: Path, output_dir: Path) -> list[str]:
    count = len(RENDITIONS)

    split_labels = "".join(f"[v{i}]" for i in range(count))
    filters = [f"[0:v]split={count}{split_labels}"]
    for i, rendition in enumerate(RENDITIONS):
        filters.append(f"[v{i}]scale=-2:{rendition['height']}[v{i}out]")

    command = ["ffmpeg", "-i", str(input_path), "-filter_complex", "; ".join(filters)]

    for i, rendition in enumerate(RENDITIONS):
        command += [
            "-map",
            f"[v{i}out]",
            f"-c:v:{i}",
            "libx264",
            f"-b:v:{i}",
            rendition["bitrate"],
            f"-maxrate:v:{i}",
            rendition["maxrate"],
            f"-bufsize:v:{i}",
            rendition["bufsize"],
        ]

    for i in range(count):
        command += ["-map", "0:a", f"-c:a:{i}", "aac", f"-b:a:{i}", "128k"]

    stream_map = " ".join(
        f"v:{i},a:{i},name:{rendition['name']}"
        for i, rendition in enumerate(RENDITIONS)
    )

    command += [
        "-force_key_frames",
        f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
        "-f",
        "hls",
        "-hls_time",
        str(SEGMENT_SECONDS),
        "-hls_playlist_type",
        "vod",
        "-master_pl_name",
        "master.m3u8",
        "-var_stream_map",
        stream_map,
        "-hls_segment_filename",
        # as_posix(): из этих путей ffmpeg строит ссылки внутри master.m3u8,
        # а в URL разделитель только "/". str() на Windows дал бы "1080p\playlist.m3u8".
        (output_dir / "%v" / "segment_%03d.ts").as_posix(),
        (output_dir / "%v" / "playlist.m3u8").as_posix(),
    ]

    return command


async def _transcode_video_async(video_id: int) -> None:
    async with async_session_factory() as session:
        video = await get_video_by_id(session, video_id)
        video_upload = await get_video_upload_by_video_id(session, video_id)

        set_video_status(video, VideoStatus.PROCESSING)

        await session.commit()

        hls_prefix = f"videos/{video_id}/hls"

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

                for rendition in RENDITIONS:
                    (hls_dir / rendition["name"]).mkdir()

                result = await asyncio.to_thread(
                    subprocess.run,
                    _build_ffmpeg_command(original_path, hls_dir),
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
                    s3_key = f"{hls_prefix}/{relative_path.as_posix()}"

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
            mark_video_ready(video, f"{hls_prefix}/master.m3u8")
            await session.commit()
