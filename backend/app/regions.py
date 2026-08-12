"""Data-residency helpers: resolve a request's data region from the viewer's country,
and hand back the region-appropriate S3 bucket, S3 client, and AgentCore runtime ARN.

A user's location is taken from the ``CloudFront-Viewer-Country`` header that CloudFront
injects (ISO-3166 alpha-2). All of that user's data is then stored in — and processed by —
the resolved region. Unknown/unmapped countries fall back to ``DEFAULT_DATA_REGION``.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import boto3
from fastapi import Request

from app.config import (
    COUNTRY_REGION,
    DEFAULT_DATA_REGION,
    REGION_AGENT_ARNS,
    REGION_BUCKETS,
)

logger = logging.getLogger(__name__)


def region_for_country(country_code: str | None) -> str:
    """Map an ISO-3166 alpha-2 country code to a data region (default if unmapped)."""
    if not country_code:
        return DEFAULT_DATA_REGION
    return COUNTRY_REGION.get(country_code.strip().upper(), DEFAULT_DATA_REGION)


def resolve_region(request: Request) -> str:
    """Resolve the data region for an incoming request.

    Precedence: CloudFront-Viewer-Country → X-User-Country (manual/testing override)
    → DEFAULT_DATA_REGION. Only ever returns a region we actually have a bucket for.
    """
    country = request.headers.get("cloudfront-viewer-country") or request.headers.get(
        "x-user-country"
    )
    region = region_for_country(country)
    if region not in REGION_BUCKETS:  # safety net
        region = DEFAULT_DATA_REGION
    return region


def bucket_for_region(region: str) -> str:
    return REGION_BUCKETS.get(region, REGION_BUCKETS[DEFAULT_DATA_REGION])


@lru_cache(maxsize=None)
def s3_client_for_region(region: str):
    """A cached S3 client bound to the given region (so calls hit the in-region endpoint)."""
    return boto3.client("s3", region_name=region)


def agent_arn_for_region(region: str) -> str:
    """The AgentCore runtime ARN for a region (falls back to the default region's)."""
    arn = REGION_AGENT_ARNS.get(region) or REGION_AGENT_ARNS.get(DEFAULT_DATA_REGION)
    if not arn:
        raise RuntimeError(f"No AgentCore runtime ARN configured for region {region!r}")
    return arn


# FastAPI dependency ------------------------------------------------------------------
def get_data_context(request: Request) -> dict:
    """FastAPI dependency: resolve the region and return the routing bundle for it."""
    region = resolve_region(request)
    return {
        "region": region,
        "bucket": bucket_for_region(region),
        "s3": s3_client_for_region(region),
        "agent_arn": REGION_AGENT_ARNS.get(region) or REGION_AGENT_ARNS.get(DEFAULT_DATA_REGION),
    }
