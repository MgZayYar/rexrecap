"""S3-compatible object storage backend (AWS S3, MinIO, R2, ...).

Credentials come from the environment (S3_ACCESS_KEY_ID /
S3_SECRET_ACCESS_KEY) and are never logged. All delivery happens through
presigned URLs, so large media never flows through the API process.
"""

from __future__ import annotations

from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.storage.base import StorageBackend


class S3StorageBackend:
    name = "s3"

    def __init__(self, bucket: str, endpoint_url: str | None = None,
                 region: str | None = None,
                 access_key_id: str | None = None,
                 secret_access_key: str | None = None) -> None:
        if not bucket:
            raise ValueError("S3_BUCKET must be set for the s3 storage backend")
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region or "us-east-1",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def put_file(self, key: str, path: Path, content_type: str | None = None) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.upload_file(str(path), self.bucket, key, ExtraArgs=extra or None)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_get_url(self, key: str, expires_in: int = 3600,
                          filename: str | None = None) -> str:
        params: dict = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self._client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in)
