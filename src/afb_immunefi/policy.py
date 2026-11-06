"""Policy loading and analysis gate. Policy data must be confirmed by a human."""
from pathlib import Path
from typing import Any
import yaml

REQUIRED_FLAGS = ("scope_confirmed", "testing_constraints_reviewed", "safe_harbor_reviewed")

def load_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Policy YAML must contain a mapping at its root.")
    return data

def policy_issues(policy: dict[str, Any]) -> list[str]:
    issues = []
    for key in ("program_name", "program_url", "last_checked"):
        if not str(policy.get(key, "")).strip():
            issues.append(f"Missing {key}")
    for key in REQUIRED_FLAGS:
        if policy.get(key) is not True:
            issues.append(f"{key} must be explicitly set to true after human review")
    if not policy.get("in_scope_assets"):
        issues.append("No in_scope_assets recorded")
    return issues

def require_policy(path: Path) -> dict[str, Any]:
    policy = load_policy(path)
    issues = policy_issues(policy)
    if issues:
        raise PermissionError("Policy gate is closed:\n- " + "\n- ".join(issues))
    return policy
