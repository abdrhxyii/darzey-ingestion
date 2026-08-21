"""Read-only connectivity check for the configured Cloudflare R2 bucket."""

from __future__ import annotations

import os
import sys


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    try:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=required("R2_ENDPOINT_URL"),
            aws_access_key_id=required("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=required("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
        )
        bucket = required("R2_BUCKET")
        # Listing one object is read-only and verifies bucket-scoped credentials.
        client.list_objects_v2(Bucket=bucket, MaxKeys=1)
    except Exception as error:  # pragma: no cover - exercised in Actions
        print(f"R2 connectivity check failed: {error}", file=sys.stderr)
        return 1

    print(f"R2 connectivity check passed for bucket {bucket}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
