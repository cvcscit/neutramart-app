"""The ECS scripts' templates render from ``config.env`` alone, and the helpers read and compare them safely."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from ecs import deploy_helpers
from ecs.deploy_helpers import MissingValues, RuntimeNotDeployed

ECS_DIR = deploy_helpers.ECS_DIR
REPO_ROOT = ECS_DIR.parents[1]
ACCOUNT = "123456789012"
DEPLOY_VALUES = {"AWS_ACCOUNT_ID": ACCOUNT, "IMAGE_TAG": "abc1234"}
DATA_REGION_CODES = ("US", "IN", "CA", "EU")
FAKE_ARNS = {f"AGENT_ARN_{code}": f"arn:aws:bedrock-agentcore:r:{ACCOUNT}:runtime/{code}" for code in DATA_REGION_CODES}


def _config_env() -> dict[str, str]:
    """``config.env`` as ``lib.sh`` exports it: one ``KEY=VALUE`` per line, comments on their own lines."""
    lines = (ECS_DIR / "config.env").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if line and not line.startswith("#"))


def _rendered(template: str, **extra: str) -> dict:
    return deploy_helpers.render((ECS_DIR / template).read_text(), {**_config_env(), **DEPLOY_VALUES, **extra})


def _environment(task_definition: dict) -> dict[str, str]:
    return {item["name"]: item["value"] for item in task_definition["containerDefinitions"][0]["environment"]}


def test_task_definition_renders_from_config_env_alone() -> None:
    task_definition = _rendered("task-definition.json")

    assert not re.search(r"<[A-Z][A-Z0-9_]*>", json.dumps(task_definition))
    assert task_definition["containerDefinitions"][0]["image"].endswith("/nutrasmart-backend:abc1234")
    assert task_definition["taskRoleArn"] == f"arn:aws:iam::{ACCOUNT}:role/nutrasmart-ecs-task-role"


def test_production_values_have_no_local_or_legacy_origins_or_buckets() -> None:
    environment = _environment(_rendered("task-definition.json"))

    assert environment["ALLOWED_ORIGINS"] and "localhost" not in environment["ALLOWED_ORIGINS"]
    assert all("sci-neutrasmart" not in value for value in environment.values())
    assert {"S3_BUCKET_NAME", "AGENT_RUNTIME_ARN"}.isdisjoint(environment)
    assert all(environment[f"BUCKET_{code}"] for code in DATA_REGION_CODES)


def test_lib_sh_renders_the_same_task_definition() -> None:
    script = f'source "{ECS_DIR}/lib.sh" && render task-definition.json'
    env = {"PATH": os.environ["PATH"], **DEPLOY_VALUES}
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=30, check=True)

    assert json.loads(result.stdout) == _rendered("task-definition.json")


def test_missing_values_are_all_named() -> None:
    with pytest.raises(MissingValues) as caught:
        deploy_helpers.render((ECS_DIR / "task-definition.json").read_text(), _config_env())

    assert str(caught.value) == "AWS_ACCOUNT_ID, IMAGE_TAG"


def test_values_are_json_escaped() -> None:
    rendered = deploy_helpers.render('{"a": "<A>"}', {"A": 'say "hi" \\ bye'})

    assert rendered == {"a": 'say "hi" \\ bye'}


def test_an_empty_environment_value_leaves_the_variable_unset() -> None:
    environment = _environment(_rendered("task-definition.json", ORIGIN_VERIFY_EXEMPT_ORIGINS=""))

    assert "ORIGIN_VERIFY_EXEMPT_ORIGINS" not in environment


def test_ssm_names_are_the_six_the_edge_reads() -> None:
    names = deploy_helpers.ssm_names(json.loads((ECS_DIR / "task-definition.json").read_text()))

    agent_arns = [f"agent-arn-{code.lower()}" for code in DATA_REGION_CODES]
    assert names == ["google-client-id", "cf-origin-secret", *agent_arns]


def test_task_role_policy_names_only_the_data_buckets_and_the_four_runtimes() -> None:
    statements = _rendered("task-role-policy.json", **FAKE_ARNS)["Statement"]
    buckets = [_config_env()[f"BUCKET_{code}"] for code in DATA_REGION_CODES]
    runtimes = [FAKE_ARNS[f"AGENT_ARN_{code}"] for code in DATA_REGION_CODES]
    by_sid = {statement["Sid"]: statement for statement in statements}

    assert by_sid["UserObjects"]["Resource"] == [f"arn:aws:s3:::{bucket}/users/*" for bucket in buckets]
    assert by_sid["ListUserPrefixes"]["Resource"] == [f"arn:aws:s3:::{bucket}" for bucket in buckets]
    assert by_sid["ListUserPrefixes"]["Condition"] == {"StringLike": {"s3:prefix": "users/*"}}
    # The runtime and its endpoints: an invocation is authorized against both.
    invoke = by_sid["InvokeRegionalAgents"]["Resource"]
    assert invoke == [arn for runtime in runtimes for arn in (runtime, f"{runtime}/*")]
    assert all(statement["Resource"] != "*" for statement in statements)


def test_runtime_arns_come_from_each_regions_agentcore_project() -> None:
    regions = {"us": "us-east-1", "in": "ap-south-1", "ca": "ca-central-1", "eu": "eu-west-1"}

    for code, region in regions.items():
        assert deploy_helpers.runtime_arn(REPO_ROOT, code).startswith(f"arn:aws:bedrock-agentcore:{region}:")


def test_a_region_without_deployed_state_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RuntimeNotDeployed):
        deploy_helpers.runtime_arn(tmp_path, "eu")


def test_diff_lists_changed_added_and_removed_fields() -> None:
    live = _rendered("task-definition.json", IMAGE_TAG="latest")
    live["containerDefinitions"][0]["environment"].append({"name": "S3_BUCKET_NAME", "value": "old-bucket"})
    new = _rendered("task-definition.json")
    new["containerDefinitions"][0]["secrets"].pop()

    changes = deploy_helpers.diff(live, new)

    assert any(line.startswith("~ image:") and line.endswith(":abc1234") for line in changes)
    assert "- env S3_BUCKET_NAME = old-bucket" in changes
    assert any(line.startswith("- secret AGENT_ARN_EU = arn:aws:ssm:") for line in changes)
    assert deploy_helpers.diff(new, new) == []


def test_diff_never_prints_a_plain_text_secret() -> None:
    live = _rendered("task-definition.json")
    live["containerDefinitions"][0]["environment"].append({"name": "CF_ORIGIN_SECRET", "value": "s3cr3t-value"})

    changes = deploy_helpers.diff(live, _rendered("task-definition.json"))

    assert changes == ["- env CF_ORIGIN_SECRET = (value hidden)"]
