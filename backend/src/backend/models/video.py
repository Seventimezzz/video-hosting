from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class VideoStatus(str, Enum):
    PENDING = "pending"  # метаданные созданы, файла ещё нет, загрузка не начата
    UPLOADING = "uploading"  # чанки принимаются, файл ещё не собран
    UPLOADED = "uploaded"  # файл собран и лежит в MinIO как есть
    PROCESSING = "processing"  # задача транскодирования взята воркером
    READY = "ready"  # HLS готов, можно стримить
    FAILED = "failed"  # ошибка на любом из шагов (upload или transcode)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    description: Mapped[str]
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[VideoStatus] = mapped_column(default=VideoStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
