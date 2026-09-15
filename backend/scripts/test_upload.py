"""
Ручной тестовый клиент для chunked upload (Этап 3).

Запуск (сервер должен быть уже поднят, например `uv run uvicorn backend.main:app`):

    uv run python scripts/test_upload.py path/to/file.mp4

По умолчанию логинится как test@example.com / password123, регистрируя
пользователя при первом запуске, если его ещё нет.
"""

import sys
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "test@example.com"
PASSWORD = "password123"


def ensure_logged_in(client: httpx.Client) -> None:
    response = client.post(
        "/login", json={"email": EMAIL, "password": PASSWORD}
    )
    if response.status_code == 200:
        print(f"Logged in as {EMAIL}")
        return

    print(f"Login failed ({response.status_code}), registering {EMAIL}...")
    response = client.post(
        "/register", json={"email": EMAIL, "password": PASSWORD}
    )
    response.raise_for_status()

    response = client.post("/login", json={"email": EMAIL, "password": PASSWORD})
    response.raise_for_status()
    print(f"Registered and logged in as {EMAIL}")


def create_video(client: httpx.Client, title: str) -> int:
    response = client.post(
        "/videos", json={"title": title, "description": "test upload"}
    )
    response.raise_for_status()
    video = response.json()
    print(f"Created video id={video['id']} status={video['status']}")
    return video["id"]


def start_upload(client: httpx.Client, video_id: int, total_size: int) -> int:
    response = client.post(
        f"/videos/{video_id}/upload", json={"total_size": total_size}
    )
    response.raise_for_status()
    data = response.json()
    print(f"Started upload: status={data['status']} chunk_size={data['chunk_size']}")
    return data["chunk_size"]


def upload_chunks(
    client: httpx.Client, video_id: int, file_path: Path, chunk_size: int
) -> None:
    with file_path.open("rb") as f:
        chunk_number = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break

            response = client.put(
                f"/videos/{video_id}/upload/chunks/{chunk_number}",
                content=chunk,
            )
            response.raise_for_status()
            print(f"Uploaded chunk {chunk_number} ({len(chunk)} bytes)")
            chunk_number += 1


def complete_upload(client: httpx.Client, video_id: int) -> None:
    response = client.post(f"/videos/{video_id}/upload/complete")
    response.raise_for_status()
    video = response.json()
    print(f"Completed upload: status={video['status']}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_upload.py <path-to-file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.is_file():
        print(f"File not found: {file_path}")
        sys.exit(1)

    total_size = file_path.stat().st_size

    with httpx.Client(base_url=BASE_URL) as client:
        ensure_logged_in(client)
        video_id = create_video(client, title=file_path.name)
        chunk_size = start_upload(client, video_id, total_size)
        upload_chunks(client, video_id, file_path, chunk_size)
        complete_upload(client, video_id)


if __name__ == "__main__":
    main()
