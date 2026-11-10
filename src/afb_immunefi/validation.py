"""Local Foundry validation and differential test-outcome comparison."""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path


def _extract_test_statuses(value, output=None):
    output = output if output is not None else {}
    if isinstance(value, dict):
        test = value.get("test") or value.get("test_name") or value.get("name")
        status = value.get("status") or value.get("result")
        if isinstance(test, str) and isinstance(status, str):
            output[test.split("(")[0]] = status.lower()
        for child in value.values():
            _extract_test_statuses(child, output)
    elif isinstance(value, list):
        for child in value:
            _extract_test_statuses(child, output)
    return output


def _run_forge_json(project: Path, *, timeout=1800, match_test=None):
    if not project.is_dir():
        raise NotADirectoryError(f"Foundry project does not exist: {project}")
    forge = shutil.which("forge")
    if not forge:
        raise FileNotFoundError("Foundry forge is not installed.")
    command = [forge, "test", "--json"]
    if match_test:
        command.extend(["--match-test", match_test])
    proc = subprocess.run(command, cwd=project.resolve(), capture_output=True, text=True, timeout=timeout, check=False)
    parsed = None
    parse_error = None
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError as exc:
        parse_error = str(exc)
    statuses = _extract_test_statuses(parsed) if parsed is not None else {}
    return {
        "command": command,
        "returncode": proc.returncode,
        "parsed": parsed is not None,
        "parse_error": parse_error,
        "test_statuses": statuses,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }


def run_forge_validation(project: Path, test_map_path: Path, output: Path, *, timeout=1800):
    """Run local tests mapped to finding IDs; test failures remain triage items."""
    mapping = json.loads(test_map_path.read_text(encoding="utf-8"))
    finding_tests = mapping.get("finding_tests", {})
    if not isinstance(finding_tests, dict) or not finding_tests:
        raise ValueError("test map must contain a non-empty finding_tests object")
    result = _run_forge_json(project, timeout=timeout)
    validations = []
    for finding_id, test_name in finding_tests.items():
        status = result["test_statuses"].get(str(test_name))
        validations.append({
            "finding_id": finding_id,
            "test_name": test_name,
            "test_status": status or "not_found_in_forge_json",
            "interpretation": (
                "failed_test_requires_manual_reproduction_and_root_cause_review"
                if status and status not in {"success", "passed"}
                else "test_passed_no_counterexample_in_this_run"
                if status else "test_not_observed"
            ),
        })
    report = {
        "schema_version": 1,
        "project": str(project.resolve()),
        "forge_returncode": result["returncode"],
        "json_parsed": result["parsed"],
        "validations": validations,
        "all_findings_confirmed": False,
        "warning": "A failing test is not automatically a vulnerability; inspect assertion, trace, preconditions and scope. A passing test does not prove absence of a bug.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run_forge_differential(reference: Path, candidate: Path, output: Path, *, timeout=1800):
    """Compare the same Foundry test outcomes across two local source snapshots."""
    before = _run_forge_json(reference, timeout=timeout)
    after = _run_forge_json(candidate, timeout=timeout)
    before_tests = before["test_statuses"]
    after_tests = after["test_statuses"]
    changes = []
    for name in sorted(set(before_tests) | set(after_tests)):
        left, right = before_tests.get(name), after_tests.get(name)
        if left != right:
            changes.append({"test": name, "reference": left, "candidate": right})
    report = {
        "schema_version": 1,
        "reference": str(reference.resolve()),
        "candidate": str(candidate.resolve()),
        "reference_returncode": before["returncode"],
        "candidate_returncode": after["returncode"],
        "reference_json_parsed": before["parsed"],
        "candidate_json_parsed": after["parsed"],
        "reference_test_count": len(before_tests),
        "candidate_test_count": len(after_tests),
        "changed_test_outcomes": changes,
        "interpretation": "Test outcome differences require investigation; this is not EVM state equivalence or a security verdict.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
