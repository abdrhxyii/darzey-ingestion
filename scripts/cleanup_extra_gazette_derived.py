"""Remove only the temporary Extra Gazette artifacts created under ``derived/``."""

from __future__ import annotations

import os


PREFIX = "derived/extra-gazette/"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=required("R2_ENDPOINT_URL"),
        aws_access_key_id=required("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=required("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )
    bucket = required("R2_BUCKET")
    paginator = client.get_paginator("list_objects_v2")
    keys = [
        {"Key": item["Key"]}
        for page in paginator.paginate(Bucket=bucket, Prefix=PREFIX)
        for item in page.get("Contents", [])
    ]

    for start in range(0, len(keys), 1000):
        client.delete_objects(Bucket=bucket, Delete={"Objects": keys[start : start + 1000], "Quiet": True})

    print(f"Deleted {len(keys)} temporary artifacts under {PREFIX}")


if __name__ == "__main__":
    main()
