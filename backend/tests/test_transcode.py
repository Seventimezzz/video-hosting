import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from backend.config import settings
from backend.database import async_session_factory
from backend.models.video import VideoStatus
from backend.models.video_upload import VideoUpload
from backend.repositories.video_repository import get_video_by_id, set_video_status
from backend.tasks import (
    RENDITIONS,
    TranscodeError,
    _build_ffmpeg_command,
    _transcode_video_async,
)
from conftest import create_video as _create_video
from conftest import register_and_login as _register_and_login
from httpx import ASGITransport, AsyncClient

from backend import app


@pytest.fixture
def mock_s3():
    with patch("backend.tasks.s3_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_ffmpeg():
    with patch("backend.tasks.subprocess.run") as mock_run:
        yield mock_run


def _fake_ffmpeg_success(command, **kwargs):
    # Последний аргумент команды: <hls_dir>/%v/playlist.m3u8. Кладём в hls_dir
    # те же файлы, что создал бы настоящий ffmpeg, чтобы задаче было что
    # загружать в MinIO.
    hls_dir = Path(command[-1]).parent.parent
    (hls_dir / "master.m3u8").write_text("#EXTM3U\n")
    for rendition in RENDITIONS:
        rendition_dir = hls_dir / rendition["name"]
        (rendition_dir / "playlist.m3u8").write_text("#EXTM3U\n")
        (rendition_dir / "segment_000.ts").write_bytes(b"ts")
    return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")


async def _create_uploaded_video(email: str) -> int:
    # Переводим видео в состояние "файл загружен в MinIO", минуя чанки:
    # протокол загрузки уже покрыт в test_video_upload.py.
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await _register_and_login(client, email)
        video_id = await _create_video(client)

    async with async_session_factory() as session:
        video = await get_video_by_id(session, video_id)
        video.status = VideoStatus.UPLOADED
        session.add(
            VideoUpload(
                video_id=video_id,
                total_size=100,
                storage_path=f"videos/{video_id}/original.mp4",
            )
        )
        await session.commit()

    return video_id


async def _get_status(video_id: int) -> VideoStatus:
    async with async_session_factory() as session:
        video = await get_video_by_id(session, video_id)
        return video.status


async def test_transcode_success_uploads_hls_and_marks_ready(
    unique_email, mock_s3, mock_ffmpeg
):
    mock_ffmpeg.side_effect = _fake_ffmpeg_success
    video_id = await _create_uploaded_video(unique_email)

    with patch("backend.tasks.set_video_status", wraps=set_video_status) as status_spy:
        await _transcode_video_async(video_id)

    assert await _get_status(video_id) == VideoStatus.READY
    assert [call.args[1] for call in status_spy.call_args_list] == [
        VideoStatus.PROCESSING,
        VideoStatus.READY,
    ]

    mock_s3.download_file.assert_called_once()
    assert mock_s3.download_file.call_args.args[:2] == (
        settings.minio_bucket,
        f"videos/{video_id}/original.mp4",
    )

    uploaded_keys = {call.args[2] for call in mock_s3.upload_file.call_args_list}
    expected_keys = {f"videos/{video_id}/hls/master.m3u8"}
    for rendition in RENDITIONS:
        for file_name in ("playlist.m3u8", "segment_000.ts"):
            expected_keys.add(f"videos/{video_id}/hls/{rendition['name']}/{file_name}")
    assert uploaded_keys == expected_keys
    assert all(
        call.args[1] == settings.minio_bucket
        for call in mock_s3.upload_file.call_args_list
    )


async def test_transcode_marks_failed_when_ffmpeg_fails(
    unique_email, mock_s3, mock_ffmpeg
):
    mock_ffmpeg.return_value = subprocess.CompletedProcess(
        [], returncode=1, stdout="", stderr="Invalid data found when processing input"
    )
    video_id = await _create_uploaded_video(unique_email)

    with pytest.raises(TranscodeError, match="Invalid data found"):
        await _transcode_video_async(video_id)

    assert await _get_status(video_id) == VideoStatus.FAILED
    mock_s3.upload_file.assert_not_called()


async def test_transcode_marks_failed_when_download_fails(
    unique_email, mock_s3, mock_ffmpeg
):
    mock_s3.download_file.side_effect = Exception("minio unavailable")
    video_id = await _create_uploaded_video(unique_email)

    with pytest.raises(Exception, match="minio unavailable"):
        await _transcode_video_async(video_id)

    assert await _get_status(video_id) == VideoStatus.FAILED
    mock_ffmpeg.assert_not_called()


async def test_transcode_marks_failed_when_hls_upload_fails(
    unique_email, mock_s3, mock_ffmpeg
):
    mock_ffmpeg.side_effect = _fake_ffmpeg_success
    mock_s3.upload_file.side_effect = Exception("minio unavailable")
    video_id = await _create_uploaded_video(unique_email)

    with pytest.raises(Exception, match="minio unavailable"):
        await _transcode_video_async(video_id)

    assert await _get_status(video_id) == VideoStatus.FAILED


def test_build_ffmpeg_command_has_variant_per_rendition():
    command = _build_ffmpeg_command(Path("in.mp4"), Path("out"))

    filter_graph = command[command.index("-filter_complex") + 1]
    assert filter_graph.startswith(f"[0:v]split={len(RENDITIONS)}")
    for rendition in RENDITIONS:
        # -2 вместо фиксированной ширины: пропорции исходника сохраняются.
        assert f"scale=-2:{rendition['height']}" in filter_graph

    # На каждое качество один видео- и один аудиопоток.
    assert command.count("-map") == 2 * len(RENDITIONS)

    assert command[command.index("-var_stream_map") + 1] == (
        "v:0,a:0,name:1080p v:1,a:1,name:720p v:2,a:2,name:480p"
    )
    assert command[command.index("-master_pl_name") + 1] == "master.m3u8"
    # Только прямые слэши: ffmpeg берёт из этих путей ссылки для master.m3u8,
    # и "\" на Windows сломал бы плейлист (браузер запросит 1080p%5Cplaylist.m3u8).
    assert command[-1] == "out/%v/playlist.m3u8"
    segment_pattern = command[command.index("-hls_segment_filename") + 1]
    assert segment_pattern == "out/%v/segment_%03d.ts"
