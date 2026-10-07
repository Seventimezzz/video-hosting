"""
Подготовка MinIO к работе (Этап 5): бакет + публичное чтение HLS.

Идемпотентен — можно запускать сколько угодно раз:

    uv run python scripts/init_storage.py

Бакет создаётся, только если его нет. Политика перезаписывается целиком:
анонимам разрешено скачивать videos/<id>/hls/*, оригиналы (original.mp4)
и листинг бакета остаются закрытыми.
"""

import json

from backend.config import settings
from backend.storage import s3_client
from botocore.exceptions import ClientError


def ensure_bucket(bucket: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' already exists")
    except ClientError as err:
        code = err.response["Error"]["Code"]
        if code != "404":
            # 403 (неверные ключи) и прочее — не «бакета нет», а реальная проблема.
            raise
        s3_client.create_bucket(Bucket=bucket)
        print(f"Bucket '{bucket}' created")


def apply_public_hls_policy(bucket: str) -> None:
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/videos/*/hls/*"],
            }
        ],
    }
    s3_client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
    print(f"Public read policy applied to '{bucket}/videos/*/hls/*'")


def main() -> None:
    bucket = settings.minio_bucket
    ensure_bucket(bucket)
    apply_public_hls_policy(bucket)


if __name__ == "__main__":
    main()
