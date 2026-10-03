"""Construction of the agent's external dependencies (AWS clients, food classifier).

Nothing here runs at import time: ``build_services`` is called on the first
invocation and the result is reused for the life of the container. The classifier is
loaded lazily on the first ``analyze`` request so chat/summary never pay for torch.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import boto3
from botocore.config import Config

from .recognition import ClassifierError, FoodClassifier, build_classifier
from .settings import AgentSettings

logger = logging.getLogger(__name__)


class LazyClassifier:
    """Loads the configured classifier once; ``get()`` returns ``None`` if disabled or broken.

    A load failure is logged and remembered so the agent keeps serving through the
    vision-LLM path instead of retrying a failing download on every request.
    """

    def __init__(self, settings: AgentSettings, s3_client) -> None:
        self._settings = settings
        self._s3 = s3_client
        self._lock = threading.Lock()
        self._loaded = False
        self._classifier: FoodClassifier | None = None

    def get(self) -> FoodClassifier | None:
        if not self._settings.classifier.enabled:
            return None
        with self._lock:
            if not self._loaded:
                self._classifier = self._load()
                self._loaded = True
        return self._classifier

    def _load(self) -> FoodClassifier | None:
        try:
            return build_classifier(self._settings.classifier, self._s3)
        except ClassifierError:
            logger.exception("Food classifier unavailable; using vision LLM only")
            return None


@dataclass(frozen=True)
class AgentServices:
    """Everything the action handlers need, injected rather than global."""

    settings: AgentSettings
    s3: object
    bedrock: object
    bedrock_config: Config
    classifier: LazyClassifier = field(repr=False)


def _client_config(connect_timeout: float, read_timeout: float, max_retries: int) -> Config:
    return Config(
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries={"max_attempts": max_retries, "mode": "standard"},
    )


def build_services(settings: AgentSettings) -> AgentServices:
    """Create AWS clients with explicit timeouts and a lazy classifier."""
    # S3 client targets the bucket's region; Bedrock uses the runtime region.
    s3 = boto3.client(
        "s3",
        region_name=settings.s3_region,
        config=_client_config(settings.s3_connect_timeout_s, settings.s3_read_timeout_s, settings.max_retries),
    )
    bedrock_config = _client_config(
        settings.bedrock_connect_timeout_s, settings.bedrock_read_timeout_s, settings.max_retries
    )
    bedrock = boto3.client("bedrock-runtime", region_name=settings.bedrock_region, config=bedrock_config)
    return AgentServices(
        settings=settings,
        s3=s3,
        bedrock=bedrock,
        bedrock_config=bedrock_config,
        classifier=LazyClassifier(settings, s3),
    )
