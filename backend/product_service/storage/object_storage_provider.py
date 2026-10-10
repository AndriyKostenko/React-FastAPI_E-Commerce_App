"""Builds the catalogue and private stores for the configured backend."""

from functools import lru_cache
from pathlib import Path
from typing import cast

import boto3
from botocore.config import Config

from shared.settings import Settings, get_settings
from storage.object_store import (
    LocalObjectStore,
    ObjectStorageNotConfiguredError,
    ObjectStore,
    S3Client,
    S3ObjectStore,
)


class S3ClientFactory:
    """One boto3 client per process, shared by both stores (it is thread-safe)."""

    @staticmethod
    def create(settings: Settings) -> S3Client:
        credentials: dict[str, str] = {}
        if settings.AWS_S3_ACCESS_KEY_ID and settings.AWS_S3_SECRET_ACCESS_KEY:
            # An S3-compatible server (the local SeaweedFS). In AWS both are
            # unset and the default chain finds the workload role.
            credentials = {
                "aws_access_key_id": settings.AWS_S3_ACCESS_KEY_ID.get_secret_value(),
                "aws_secret_access_key": settings.AWS_S3_SECRET_ACCESS_KEY.get_secret_value(),
            }
        config = Config(
            signature_version="s3v4",
            # A custom endpoint has no per-bucket DNS names: address buckets
            # by path (http://host:port/<bucket>/<key>).
            s3={"addressing_style": "path" if settings.AWS_S3_ENDPOINT_URL else "auto"},
            retries={"max_attempts": 3, "mode": "standard"},
        )
        client = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            config=config,
            **credentials,
        )
        return cast(S3Client, client)


class ObjectStorageProvider:
    """The two stores, built lazily so a process only needs the settings of
    the store it actually uses."""

    def __init__(self, settings: Settings, s3_client: S3Client | None = None) -> None:
        self._settings = settings
        self._s3_client = s3_client
        self._catalogue: ObjectStore | None = None
        self._private: ObjectStore | None = None

    @property
    def backend(self) -> str:
        return self._settings.OBJECT_STORAGE_BACKEND

    def catalogue(self) -> ObjectStore:
        if self._catalogue is None:
            self._catalogue = self._build("AWS_S3_CATALOGUE_BUCKET", self._settings.AWS_S3_CATALOGUE_BUCKET)
        return self._catalogue

    def private(self) -> ObjectStore:
        if self._private is None:
            self._private = self._build("AWS_S3_PRIVATE_BUCKET", self._settings.AWS_S3_PRIVATE_BUCKET)
        return self._private

    def _build(self, setting_name: str, bucket: str | None) -> ObjectStore:
        if self.backend == "local":
            return LocalObjectStore(Path(self._settings.MEDIA_ROOT))
        if not bucket:
            raise ObjectStorageNotConfiguredError(f"{setting_name} is required when OBJECT_STORAGE_BACKEND=s3")
        if self._s3_client is None:
            self._s3_client = S3ClientFactory.create(self._settings)
        return S3ObjectStore(self._s3_client, bucket, kms_key_id=self._settings.AWS_S3_KMS_KEY_ID)


@lru_cache
def get_object_storage_provider() -> ObjectStorageProvider:
    return ObjectStorageProvider(get_settings())
