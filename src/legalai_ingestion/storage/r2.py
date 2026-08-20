from __future__ import annotations

from typing import Any


class R2ObjectStore:
    """S3-compatible Cloudflare R2 adapter; requires the optional boto3 extra."""

    def __init__(self, *, bucket: str, endpoint_url: str, access_key_id: str, secret_access_key: str) -> None:
        import boto3

        self.bucket = bucket
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def put(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            Metadata=metadata,
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
