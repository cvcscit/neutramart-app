#!/usr/bin/env python3
"""Summarize a CloudFormation change set and flag the changes that can lose data or widen access.

Reads the JSON of ``aws cloudformation describe-change-set ... --output json`` from a
file or standard input, so the script itself makes no AWS call. It prints one row
per resource change, riskiest first:

- ``DATA``: a resource that holds data, identities or a public endpoint
  (a DynamoDB table, a user pool, a secret, a bucket, a log group, an API, an
  AgentCore runtime, ...)
  is removed or replaced. Replacing it creates an empty one, or a new ID or URL
  that clients do not know.
- ``ACCESS``: an IAM role or policy, or a resource policy, is added, changed or
  removed. Read the policy diff before executing.
- ``REPLACE``: any other resource is replaced.

Exit status: 0 when nothing is flagged ``DATA``, 1 when something is, 2 when the
change set cannot be reviewed (it failed, or the listing is truncated).

Usage:
    aws cloudformation describe-change-set --change-set-name <arn> --region <region> --output json \\
        | review_change_set.py
    review_change_set.py change-set.json
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

# Types whose removal or replacement loses data, identities, or an address clients depend on.
STATEFUL_TYPES: Mapping[str, str] = {
    "AWS::DynamoDB::Table": "table data",
    "AWS::DynamoDB::GlobalTable": "table data",
    "AWS::S3::Bucket": "objects",
    "AWS::Cognito::UserPool": "users and their passwords",
    "AWS::Cognito::UserPoolClient": "the client ID the frontend uses",
    "AWS::Cognito::UserPoolGroup": "group memberships",
    "AWS::SecretsManager::Secret": "the secret value",
    "AWS::KMS::Key": "the key, and every ciphertext under it",
    "AWS::Logs::LogGroup": "logs (the audit trail)",
    "AWS::ECR::Repository": "images",
    "AWS::BedrockAgentCore::Runtime": "the runtime ARN the edge and SSM point at",
    "AWS::BedrockAgentCore::RuntimeEndpoint": "the endpoint clients invoke",
    "AWS::ApiGatewayV2::Api": "the API's URL",
    "AWS::ApiGatewayV2::Stage": "the API stage's URL",
    "AWS::CloudFront::Distribution": "the distribution's domain name",
}
ACCESS_TYPES: frozenset[str] = frozenset(
    {
        "AWS::IAM::Role",
        "AWS::IAM::Policy",
        "AWS::IAM::ManagedPolicy",
        "AWS::IAM::RolePolicy",
        "AWS::Lambda::Permission",
        "AWS::S3::BucketPolicy",
        "AWS::SecretsManager::ResourcePolicy",
    }
)
REPLACING: frozenset[str] = frozenset({"True", "Conditional"})


class Risk(IntEnum):
    """How much a change needs a human look; higher sorts first."""

    NONE = 0
    REPLACE = 1
    ACCESS = 2
    DATA = 3


@dataclass(frozen=True)
class Change:
    """One resource change from a change set."""

    action: str
    logical_id: str
    physical_id: str
    resource_type: str
    replacement: str
    policy_action: str

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> "Change":
        """Build a change from one ``Changes[].ResourceChange`` object of the API response."""
        return cls(
            action=str(raw.get("Action", "")),
            logical_id=str(raw.get("LogicalResourceId", "")),
            physical_id=str(raw.get("PhysicalResourceId", "")),
            resource_type=str(raw.get("ResourceType", "")),
            replacement=str(raw.get("Replacement", "")),
            policy_action=str(raw.get("PolicyAction", "")),
        )

    @property
    def replaces(self) -> bool:
        """Whether CloudFormation will (or may) create a new physical resource."""
        return self.action == "Modify" and self.replacement in REPLACING

    @property
    def risk(self) -> Risk:
        """Classify the change; see the module docstring for what each level means."""
        loses_resource: bool = self.action == "Remove" or self.replaces
        if loses_resource and self.resource_type in STATEFUL_TYPES:
            return Risk.DATA
        if self.resource_type in ACCESS_TYPES:
            return Risk.ACCESS
        if self.replaces:
            return Risk.REPLACE
        return Risk.NONE

    def note(self) -> str:
        """Say what is at stake for a flagged change."""
        if self.risk is Risk.DATA:
            verb: str = "removed" if self.action == "Remove" else f"replaced ({self.replacement})"
            kept: str = f", policy {self.policy_action}" if self.policy_action else ""
            return f"{verb}: loses {STATEFUL_TYPES[self.resource_type]}{kept}"
        if self.risk is Risk.ACCESS:
            return "permissions change: read the policy diff"
        if self.risk is Risk.REPLACE:
            return f"replaced ({self.replacement})"
        return ""


def load_response(source: Path | None) -> dict[str, Any]:
    """Read the describe-change-set JSON from a file, or from standard input when no file is given."""
    text: str = source.read_text(encoding="utf-8") if source else sys.stdin.read()
    data: object = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("expected the JSON object printed by `aws cloudformation describe-change-set`")
    return data


def resource_changes(response: Mapping[str, Any]) -> list[Change]:
    """Extract the resource changes, riskiest first, then by logical ID."""
    changes: list[Change] = [
        Change.from_api(item["ResourceChange"])
        for item in response.get("Changes", [])
        if item.get("Type") == "Resource" and "ResourceChange" in item
    ]
    return sorted(changes, key=lambda change: (-change.risk, change.logical_id))


def render(changes: Sequence[Change]) -> str:
    """Format the changes as an aligned text table."""
    header: tuple[str, ...] = ("RISK", "ACTION", "LOGICAL ID", "TYPE", "NOTE")
    rows: list[tuple[str, ...]] = [
        (c.risk.name if c.risk else "-", c.action, c.logical_id, c.resource_type, c.note()) for c in changes
    ]
    widths: list[int] = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header) - 1)]
    lines: list[str] = [
        "  ".join(cell.ljust(width) for cell, width in zip(row[:-1], widths, strict=True)) + "  " + row[-1]
        for row in [header, *rows]
    ]
    return "\n".join(line.rstrip() for line in lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the review and return the exit status described in the module docstring."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", nargs="?", type=Path, help="describe-change-set JSON (default: standard input)")
    args: argparse.Namespace = parser.parse_args(argv)
    response: dict[str, Any] = load_response(args.file)

    print(f"stack {response.get('StackName', '?')}, change set {response.get('ChangeSetName', '?')}")
    status: str = str(response.get("Status", ""))
    if status == "FAILED":
        print(f"change set FAILED: {response.get('StatusReason', 'no reason given')}")
        return 2
    changes: list[Change] = resource_changes(response)
    print(render(changes))
    counts: dict[Risk, int] = {risk: sum(change.risk is risk for change in changes) for risk in Risk}
    print(
        f"{len(changes)} change(s): {counts[Risk.DATA]} DATA, {counts[Risk.ACCESS]} ACCESS, "
        f"{counts[Risk.REPLACE]} REPLACE; status {status or '?'}"
    )
    if response.get("NextToken"):
        print("truncated: the listing has a NextToken; re-run describe-change-set without --max-items or --no-paginate")
        return 2
    return 1 if counts[Risk.DATA] else 0


if __name__ == "__main__":
    sys.exit(main())
