"""Resolve a model URI to a local file, downloading from S3 when needed.

``s3://bucket/key`` objects are cached under ``cache_dir`` keyed by bucket, key and
ETag, so replacing the object in S3 causes a fresh download on the next cold start.
Any other value is treated as a local filesystem path (useful for local development).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from .base import ClassifierError

logger = logging.getLogger(__name__)

_S3_SCHEME = "s3"


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    bucket, key = parsed.netloc, parsed.path.lstrip("/")
    if not bucket or not key:
        raise ClassifierError(f"Invalid S3 model URI: {uri!r}")
    return bucket, key


def _download(s3_client, bucket: str, key: str, cache_dir: Path) -> Path:
    etag = s3_client.head_object(Bucket=bucket, Key=key)["ETag"].strip('"')
    target = cache_dir / bucket / key / etag / Path(key).name
    if target.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    logger.info("food_classifier_download %s", json.dumps({"bucket": bucket, "key": key, "etag": etag}))
    s3_client.download_file(bucket, key, str(partial))
    os.replace(partial, target)  # atomic: a crash never leaves a half-written model
    return target


def resolve_model_path(uri: str, cache_dir: str, s3_client) -> Path:
    """Return a local path for ``uri``, downloading ``s3://`` objects into ``cache_dir``."""
    if urlparse(uri).scheme == _S3_SCHEME:
        bucket, key = _parse_s3_uri(uri)
        try:
            return _download(s3_client, bucket, key, Path(cache_dir))
        except ClassifierError:
            raise
        except Exception as exc:
            raise ClassifierError(f"Could not download model {uri}: {exc}") from exc

    path = Path(uri)
    if not path.is_file():
        raise ClassifierError(f"Model file not found: {path}")
    return path
