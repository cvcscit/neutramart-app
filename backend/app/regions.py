"""Data-residency helpers: resolve a request's data region from the viewer's country,
and hand back the region-appropriate S3 bucket, S3 client, and AgentCore runtime ARN.

A user's location is taken from the ``CloudFront-Viewer-Country`` header that CloudFront
injects (ISO-3166 alpha-2). All of that user's data is then stored in — and processed by —
the resolved region. Unknown/unmapped countries go to ``DEFAULT_DATA_REGION`` by design.
A region whose bucket or runtime ARN is not configured is refused (``RegionNotConfigured``,
answered with 503 by ``app.main``); it never falls back to another region's resources.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import boto3
from botocore.config import Config
from fastapi import Request

from app.config import (
    AGENT_LOCAL_URL,
    AWS_MAX_RETRIES,
    COUNTRY_REGION,
    DEFAULT_DATA_REGION,
    REGION_AGENT_ARNS,
    REGION_BUCKETS,
    S3_CONNECT_TIMEOUT_S,
    S3_READ_TIMEOUT_S,
)

logger = logging.getLogger(__name__)


class RegionNotConfigured(Exception):
    """The request's data region has no bucket, or no agent runtime ARN, configured."""

    def __init__(self, region: str) -> None:
        super().__init__(f"Data region {region!r} is not configured")
        self.region = region


def region_for_country(country_code: str | None) -> str:
    """Map an ISO-3166 alpha-2 country code to a data region (default if unmapped)."""
    if not country_code:
        return DEFAULT_DATA_REGION
    return COUNTRY_REGION.get(country_code.strip().upper(), DEFAULT_DATA_REGION)


def resolve_region(request: Request) -> str:
    """Resolve the data region for an incoming request.

    Precedence: CloudFront-Viewer-Country → X-User-Country (manual/testing override)
    → DEFAULT_DATA_REGION.
    """
    country = request.headers.get("cloudfront-viewer-country") or request.headers.get(
        "x-user-country"
    )
    return region_for_country(country)


@lru_cache(maxsize=None)
def s3_client_for_region(region: str):
    """A cached S3 client bound to the given region (so calls hit the in-region endpoint)."""
    config = Config(
        connect_timeout=S3_CONNECT_TIMEOUT_S,
        read_timeout=S3_READ_TIMEOUT_S,
        retries={"max_attempts": AWS_MAX_RETRIES, "mode": "standard"},
    )
    return boto3.client("s3", region_name=region, config=config)


# FastAPI dependency ------------------------------------------------------------------
def get_data_context(request: Request) -> dict:
    """FastAPI dependency: resolve the region and return the routing bundle for it.

    Raises ``RegionNotConfigured`` when the region has no bucket, or no runtime ARN while
    the deployed agent is in use (``AGENT_LOCAL_URL`` unset).
    """
    region = resolve_region(request)
    bucket = REGION_BUCKETS.get(region, "")
    agent_arn = REGION_AGENT_ARNS.get(region, "")
    if not bucket or not (agent_arn or AGENT_LOCAL_URL):
        logger.error(
            "data_region_not_configured region=%s bucket_set=%s agent_arn_set=%s",
            region, bool(bucket), bool(agent_arn),
        )
        raise RegionNotConfigured(region)
    return {
        "region": region,
        "bucket": bucket,
        "s3": s3_client_for_region(region),
        "agent_arn": agent_arn,
    }
