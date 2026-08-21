"""Read-only connectivity check for the configured Cloudflare R2 bucket."""

from __future__ import annotations

import os
import sys


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def validate_credential_format(access_key_id: str, secret_access_key: str) -> None:
    if len(access_key_id) != 32 or not access_key_id.isascii() or not access_key_id.isalnum():
        raise RuntimeError(
            "R2_ACCESS_KEY_ID has an invalid format; expected 32 ASCII alphanumeric characters"
        )
    if len(secret_access_key) != 64 or not secret_access_key.isascii() or not secret_access_key.isalnum():
        raise RuntimeError(
            "R2_SECRET_ACCESS_KEY has an invalid format; expected 64 ASCII alphanumeric characters"
        )


def main() -> int:
    try:
        import boto3

        endpoint_url = required("R2_ENDPOINT_URL")
        access_key_id = required("R2_ACCESS_KEY_ID")
        secret_access_key = required("R2_SECRET_ACCESS_KEY")
        bucket = required("R2_BUCKET")
        validate_credential_format(access_key_id, secret_access_key)

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )
        # Listing one object is read-only and verifies bucket-scoped credentials.
        client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    except Exception as error:  # pragma: no cover - exercised in Actions
        print(f"R2 connectivity check failed: {error}", file=sys.stderr)
        return 1

    print(f"R2 connectivity check passed for bucket {bucket}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
