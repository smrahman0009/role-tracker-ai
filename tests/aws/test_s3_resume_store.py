"""Tests for S3ResumeStore — same Protocol as FileResumeStore."""

import hashlib
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from role_tracker.aws.s3_resume_store import S3ResumeStore
from role_tracker.resume.models import ResumeMetadata

BUCKET = "role-tracker-data-test"
REGION = "ca-central-1"


@pytest.fixture
def s3_client() -> Iterator[object]:
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        yield client


@pytest.fixture
def store(s3_client: object) -> S3ResumeStore:
    return S3ResumeStore(BUCKET, s3_client=s3_client)


def test_get_metadata_returns_none_when_missing(
    store: S3ResumeStore,
) -> None:
    assert store.get_metadata("alice") is None


def test_get_file_bytes_returns_none_when_missing(
    store: S3ResumeStore,
) -> None:
    assert store.get_file_bytes("alice") is None


def test_save_then_get_metadata(store: S3ResumeStore) -> None:
    content = b"%PDF-1.4 fake resume"
    meta = store.save_resume("alice", content=content, filename="cv.pdf")
    assert isinstance(meta, ResumeMetadata)
    assert meta.filename == "cv.pdf"
    assert meta.size_bytes == len(content)
    assert meta.sha256 == hashlib.sha256(content).hexdigest()

    fetched = store.get_metadata("alice")
    assert fetched is not None
    assert fetched.filename == "cv.pdf"
    assert fetched.size_bytes == len(content)
    assert fetched.sha256 == meta.sha256


def test_save_then_get_file_bytes(store: S3ResumeStore) -> None:
    content = b"%PDF-1.4 some content"
    store.save_resume("alice", content=content, filename="cv.pdf")
    assert store.get_file_bytes("alice") == content


def test_overwrite_replaces_previous(store: S3ResumeStore) -> None:
    store.save_resume("alice", content=b"first", filename="v1.pdf")
    store.save_resume("alice", content=b"second", filename="v2.pdf")
    meta = store.get_metadata("alice")
    assert meta is not None
    assert meta.filename == "v2.pdf"
    assert store.get_file_bytes("alice") == b"second"


def test_per_user_isolation(store: S3ResumeStore) -> None:
    store.save_resume("alice", content=b"a", filename="alice.pdf")
    store.save_resume("bob", content=b"b", filename="bob.pdf")
    assert store.get_metadata("alice").filename == "alice.pdf"  # type: ignore[union-attr]
    assert store.get_metadata("bob").filename == "bob.pdf"  # type: ignore[union-attr]


def test_sha256_changes_when_content_changes(store: S3ResumeStore) -> None:
    a = store.save_resume("alice", content=b"first", filename="cv.pdf")
    b = store.save_resume("alice", content=b"second", filename="cv.pdf")
    assert a.sha256 != b.sha256
