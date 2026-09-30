"""Client for invoking a regional NutraSmart agent on Bedrock AgentCore Runtime.

The FastAPI edge resolves the user's data region, then calls ``invoke_agent`` with the
region's runtime ARN. AgentCore runtimes are regional, so the client is created per
region. The runtime returns a single JSON object which we concatenate + parse.

For local development, setting ``AGENT_LOCAL_URL`` sends every call to a locally running
agent (``POST {AGENT_LOCAL_URL}/invocations``) instead, ignoring the ARN.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

from app.config import (
    AGENT_LOCAL_TIMEOUT_S,
    AGENT_LOCAL_URL,
    AGENTCORE_REGION,
    DEFAULT_DATA_REGION,
    REGION_AGENT_ARNS,
)

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Raised when the agent runtime call fails or returns an error payload."""


@lru_cache(maxsize=None)
def _client(region: str):
    return boto3.client("bedrock-agentcore", region_name=region)


def _region_from_arn(arn: str) -> str:
    # arn:aws:bedrock-agentcore:<region>:<acct>:runtime/<id>
    try:
        return arn.split(":")[3]
    except Exception:
        return AGENTCORE_REGION


def _session_id(user_id: str) -> str:
    """Stable per-user session id (>=33 chars; AgentCore isolates state per session)."""
    return f"nutrasmart-{hashlib.sha256(user_id.encode()).hexdigest()}"


def _invoke_local(payload: dict) -> str:
    """POST the payload to the locally running agent and return the raw response body."""
    session_id = _session_id(payload.get("user_id", "anonymous"))
    try:
        response = requests.post(
            f"{AGENT_LOCAL_URL}/invocations",
            json=payload,
            headers={"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id},
            timeout=AGENT_LOCAL_TIMEOUT_S,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Local agent invocation failed (%s): %s", AGENT_LOCAL_URL, e)
        raise AgentError("Local agent invocation failed.") from e
    return response.text


def invoke_agent(payload: dict, agent_arn: str | None = None, region: str | None = None) -> dict:
    """Invoke the regional AgentCore runtime and return the parsed JSON response.

    ``agent_arn`` selects the regional runtime; if omitted it resolves from ``region``
    (or DEFAULT_DATA_REGION). With ``AGENT_LOCAL_URL`` set, the local agent is called
    instead. Raises AgentError on failure or an ``error`` payload.
    """
    raw = _invoke_local(payload) if AGENT_LOCAL_URL else _invoke_remote(payload, agent_arn, region)
    return _parse_result(raw.strip())


def _invoke_remote(payload: dict, agent_arn: str | None, region: str | None) -> str:
    """Invoke the deployed AgentCore runtime and return the concatenated response body."""
    if agent_arn is None:
        region = region or DEFAULT_DATA_REGION
        agent_arn = REGION_AGENT_ARNS.get(region) or REGION_AGENT_ARNS.get(DEFAULT_DATA_REGION)
    if not agent_arn:
        raise AgentError("No AgentCore runtime ARN configured for this region.")

    client = _client(_region_from_arn(agent_arn))
    user_id = payload.get("user_id", "anonymous")
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=_session_id(user_id),
            payload=json.dumps(payload).encode("utf-8"),
            qualifier="DEFAULT",
        )
    except (BotoCoreError, ClientError) as e:
        logger.error("AgentCore invocation failed: %s", e)
        raise AgentError("Agent runtime invocation failed.") from e

    chunks = [
        c.decode("utf-8") if isinstance(c, (bytes, bytearray)) else str(c)
        for c in response.get("response", [])
    ]
    return "".join(chunks)


def _parse_result(raw: str) -> dict:
    """Parse the agent's JSON body; raise AgentError if empty, malformed or an error payload."""
    if not raw:
        raise AgentError("Empty response from agent runtime.")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Agent returned non-JSON: %s", raw[:500])
        raise AgentError("Malformed response from agent runtime.") from e

    if isinstance(result, dict) and result.get("error"):
        raise AgentError(result["error"])
    return result
