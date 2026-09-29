"""Model URI resolution and S3 caching in ``recognition.model_store``."""

from __future__ import annotations

import pytest

from app.nutrasmart_agent.recognition import ClassifierError
from app.nutrasmart_agent.recognition.model_store import resolve_model_path


class DownloadS3:
    """Counts downloads; ETag can be changed to simulate replacing the S3 object."""

    def __init__(self, etag: str = "abc"):
        self.etag = etag
        self.downloads = 0

    def head_object(self, Bucket, Key):
        return {"ETag": f'"{self.etag}"'}

    def download_file(self, bucket, key, filename):
        self.downloads += 1
        with open(filename, "wb") as fh:
            fh.write(b"weights-" + self.etag.encode())


def test_local_path_passthrough(tmp_path):
    model = tmp_path / "m.pt"
    model.write_bytes(b"x")
    assert resolve_model_path(str(model), str(tmp_path / "cache"), s3_client=None) == model


def test_missing_local_path_raises(tmp_path):
    with pytest.raises(ClassifierError, match="not found"):
        resolve_model_path(str(tmp_path / "nope.pt"), str(tmp_path), s3_client=None)


def test_s3_downloads_once_per_etag(tmp_path):
    s3 = DownloadS3()
    uri = "s3://bucket/models/food.pt"
    first = resolve_model_path(uri, str(tmp_path), s3)
    second = resolve_model_path(uri, str(tmp_path), s3)

    assert first == second and first.read_bytes() == b"weights-abc"
    assert s3.downloads == 1
    assert not list(tmp_path.rglob("*.part"))


def test_s3_new_etag_triggers_redownload(tmp_path):
    s3 = DownloadS3()
    uri = "s3://bucket/models/food.pt"
    resolve_model_path(uri, str(tmp_path), s3)
    s3.etag = "def"
    path = resolve_model_path(uri, str(tmp_path), s3)

    assert s3.downloads == 2 and path.read_bytes() == b"weights-def"


def test_invalid_s3_uri_raises(tmp_path):
    with pytest.raises(ClassifierError, match="Invalid S3"):
        resolve_model_path("s3://bucket-only", str(tmp_path), DownloadS3())
