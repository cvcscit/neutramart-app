"""Python helpers for the edge's ECS scripts: render the JSON templates, list SSM names, diff revisions.

The templates in this directory (``task-definition.json``, ``task-role-policy.json``) hold ``<NAME>``
placeholders, each filled from the environment variable of the same name; ``lib.sh`` exports
``config.env``, ``resources.env``, ``AWS_ACCOUNT_ID``, ``IMAGE_TAG`` and the ``AGENT_ARN_*`` values before
calling this script. Standard library only, so the scripts need nothing beyond ``python3``.

Usage::

    deploy_helpers.py render TEMPLATE       # the filled-in template; exit 1 if a placeholder has no value
    deploy_helpers.py ssm-names             # the SSM parameter names task-definition.json reads, one per line
    deploy_helpers.py runtime-arn CODE      # the runtime ARN AgentCore recorded for a data region (us, in, ...)
    deploy_helpers.py diff LIVE NEW         # what NEW changes in the container compared with LIVE (JSON files)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

ECS_DIR = Path(__file__).resolve().parent
TASK_DEFINITION = ECS_DIR / "task-definition.json"
# The AgentCore CLI project that deploys each data region's runtime, relative to the repo root.
AGENT_PROJECTS: dict[str, str] = {
    "us": "backend/agent/NutrasmartAgent",
    "in": "backend/agent/regions/NutrasmartAgent-in",
    "ca": "backend/agent/regions/NutrasmartAgent-ca",
    "eu": "backend/agent/regions/NutrasmartAgent-eu",
}
_PLACEHOLDER = re.compile(r"<([A-Z][A-Z0-9_]*)>")
# Environment entries whose value the diff never prints, in case a live revision holds one in plain text.
_SENSITIVE_NAME = re.compile(r"SECRET|TOKEN|PASSWORD", re.IGNORECASE)


class MissingValues(Exception):
    """Placeholders in a template that no environment variable fills."""


class RuntimeNotDeployed(Exception):
    """The AgentCore project for a data region records no runtime ARN."""


def render(template: str, env: Mapping[str, str]) -> dict:
    """Fill every ``<NAME>`` in ``template`` from ``env`` and parse the result.

    Values are JSON-escaped, so a quote or backslash in a value cannot break the document. Raises
    ``MissingValues`` naming every placeholder ``env`` lacks; an empty value counts as present. A container
    ``environment`` entry left empty is dropped, so the variable is unset and the code default applies.
    """
    missing: list[str] = sorted({name for name in _PLACEHOLDER.findall(template) if name not in env})
    if missing:
        raise MissingValues(", ".join(missing))
    filled: dict = json.loads(_PLACEHOLDER.sub(lambda match: json.dumps(env[match.group(1)])[1:-1], template))
    for container in filled.get("containerDefinitions", []):
        if "environment" in container:
            container["environment"] = [item for item in container["environment"] if item["value"]]
    return filled


def ssm_names(task_definition: Mapping) -> list[str]:
    """The last path segment of every SSM parameter the containers' ``secrets`` read, in template order."""
    return [
        secret["valueFrom"].rsplit("/", 1)[-1]
        for container in task_definition["containerDefinitions"]
        for secret in container.get("secrets", [])
    ]


def runtime_arn(repo_root: Path, code: str) -> str:
    """The runtime ARN in the ``deployed-state.json`` of the AgentCore project that serves ``code``.

    Raises ``KeyError`` for an unknown region code and ``RuntimeNotDeployed`` when the project's state
    file is missing or names no runtime.
    """
    state_file: Path = repo_root / AGENT_PROJECTS[code] / "agentcore" / ".cli" / "deployed-state.json"
    if not state_file.is_file():
        raise RuntimeNotDeployed(f"{state_file.relative_to(repo_root)} does not exist")
    state: dict = json.loads(state_file.read_text())
    arns: list[str] = [
        runtime["runtimeArn"]
        for target in state.get("targets", {}).values()
        for runtime in target.get("resources", {}).get("runtimes", {}).values()
        if runtime.get("runtimeArn")
    ]
    if len(arns) != 1:
        raise RuntimeNotDeployed(f"{state_file.relative_to(repo_root)} names {len(arns)} runtimes, expected 1")
    return arns[0]


def _view(task_definition: Mapping) -> dict[str, str]:
    """The fields a deploy can change, flattened to comparable strings (secrets as ARNs, never values)."""
    container: Mapping = task_definition["containerDefinitions"][0]
    view: dict[str, str] = {
        "image": str(container.get("image")),
        "cpu": str(task_definition.get("cpu")),
        "memory": str(task_definition.get("memory")),
        "taskRoleArn": str(task_definition.get("taskRoleArn")),
        "executionRoleArn": str(task_definition.get("executionRoleArn")),
        "healthCheck": json.dumps(container.get("healthCheck", {}).get("command")),
    }
    view.update({f"env {item['name']}": item["value"] for item in container.get("environment", [])})
    view.update({f"secret {item['name']}": item["valueFrom"] for item in container.get("secrets", [])})
    return view


def _shown(key: str, value: str) -> str:
    """``value``, or a mask when ``key`` is an environment entry whose name looks like a secret."""
    name: str = key.removeprefix("env ")
    return "(value hidden)" if name != key and _SENSITIVE_NAME.search(name) else value


def diff(live: Mapping, new: Mapping) -> list[str]:
    """One line per changed field: ``+`` added, ``-`` removed, ``~`` changed (``old -> new``)."""
    before: dict[str, str] = _view(live)
    after: dict[str, str] = _view(new)
    lines: list[str] = []
    for key in sorted(before.keys() | after.keys()):
        if key not in after:
            lines.append(f"- {key} = {_shown(key, before[key])}")
        elif key not in before:
            lines.append(f"+ {key} = {_shown(key, after[key])}")
        elif before[key] != after[key]:
            lines.append(f"~ {key}: {_shown(key, before[key])} -> {_shown(key, after[key])}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("render").add_argument("template", type=Path)
    commands.add_parser("ssm-names")
    commands.add_parser("runtime-arn").add_argument("code", choices=sorted(AGENT_PROJECTS))
    compare = commands.add_parser("diff")
    compare.add_argument("live", type=Path)
    compare.add_argument("new", type=Path)
    args: argparse.Namespace = parser.parse_args(argv)

    try:
        if args.command == "render":
            print(json.dumps(render(args.template.read_text(), os.environ), indent=2))
        elif args.command == "ssm-names":
            print("\n".join(ssm_names(json.loads(TASK_DEFINITION.read_text()))))
        elif args.command == "runtime-arn":
            print(runtime_arn(ECS_DIR.parents[1], args.code))
        else:
            changes: list[str] = diff(json.loads(args.live.read_text()), json.loads(args.new.read_text()))
            print("\n".join(changes) if changes else "No changes to the container.")
    except MissingValues as exc:
        print(f"{args.template.name}: no value for {exc}", file=sys.stderr)
        return 1
    except RuntimeNotDeployed as exc:
        print(f"No runtime for {args.code}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
