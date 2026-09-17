import boto3

from backend.config import settings

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.minio_endpoint_url,
    aws_access_key_id=settings.minio_root_user,
    aws_secret_access_key=settings.minio_root_password,
)
