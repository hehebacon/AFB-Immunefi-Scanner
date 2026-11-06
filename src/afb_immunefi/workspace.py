"""Workspace creation and readiness checks."""

from __future__ import annotations

import json
from pathlib import Path

DIRECTORIES = (
    "program",
    "reconnaissance/sources",
    "reconnaissance/docs",
    "analysis/static",
    "analysis/review-notes",
    "findings",
    "verification/local-tests",
    "reports",
)

DEFAULT_POLICY = """# Complete this file from the selected program's official rules.
program_name: ""
program_url: ""
last_checked: ""
scope_confirmed: false
testing_constraints_reviewed: false
safe_harbor_reviewed: false
in_scope_assets: []
out_of_scope_assets: []
excluded_vulnerability_classes: []
required_impacts: []
notes: []
"""

DEFAULT_SCOPE = """# Add only assets explicitly listed as in-scope by the program.
assets: []
# Example:
# - chain: ethereum
#   address: "0x..."
#   asset_type: contract
#   status: unverified
"""

DEFAULT_FINDINGS = {"schema_version": 1, "findings": []}


def initialize_workspace(root: Path) -> list[str]:
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    for relative in DIRECTORIES:
        path = root / relative
        if not path.exists():
            path.mkdir(parents=True)
            created.append(f"{relative}/")

    templates = {
        "program/policy.yaml": DEFAULT_POLICY,
        "program/scope.yaml": DEFAULT_SCOPE,
        "findings/findings.json": json.dumps(DEFAULT_FINDINGS, indent=2) + "\n",
    }
    for relative, content in templates.items():
        path = root / relative
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(relative)

    return created


def workspace_status(root: Path) -> dict[str, object]:
    required = [
        "program/policy.yaml",
        "program/scope.yaml",
        "findings/findings.json",
        "reconnaissance/sources",
        "analysis/static",
        "verification/local-tests",
    ]
    checks = {item: (root / item).exists() for item in required}
    return {
        "workspace": str(root.resolve()),
        "exists": root.exists(),
        "ready": all(checks.values()),
        "policy_completed": _policy_completed(root / "program/policy.yaml"),
        "checks": checks,
    }


def _policy_completed(path: Path) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return (
        'program_name: ""' not in content
        and 'program_url: ""' not in content
        and "scope_confirmed: false" not in content
        and "testing_constraints_reviewed: false" not in content
    )
