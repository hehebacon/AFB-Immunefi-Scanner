"""Slither-backed semantic maps and cross-function logic review leads.

This module reports review hypotheses, not confirmed vulnerabilities. It uses Slither's
parsed contract model so analysis follows Solidity functions and state variables rather
than relying only on source-text pattern matching.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path


def _names(items) -> list[str]:
    values=[]
    for item in items or []:
        name=getattr(item, "canonical_name", None) or getattr(item, "name", None) or str(item)
        if name not in values:
            values.append(name)
    return sorted(values)


def _source_location(item) -> dict:
    mapping=getattr(item, "source_mapping", None)
    filename=getattr(mapping, "filename", None)
    relative=getattr(filename, "relative", None) or getattr(filename, "absolute", None)
    lines=list(getattr(mapping, "lines", []) or [])
    return {"file": relative, "lines": lines}


def run_logic_review(source: Path) -> dict:
    """Build entrypoint/state interaction maps and emit conservative logic-review leads."""
    if not source.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source}")

    try:
        from slither import Slither
    except ImportError as exc:
        return {
            "status": "not_installed",
            "engine": "slither-python-api",
            "error": str(exc),
            "contracts": [],
            "findings": [],
        }

    try:
        project = Slither(str(source.resolve()))
        contracts=[]
        findings=[]
        finding_index=0

        for contract in project.contracts:
            function_rows=[]
            writers=defaultdict(set)
            readers=defaultdict(set)
            state_objects={}

            for function in contract.functions_declared:
                visibility=getattr(function, "visibility", "internal")
                mutability=getattr(function, "state_mutability", "nonpayable")
                reads=_names(getattr(function, "state_variables_read", []))
                writes=_names(getattr(function, "state_variables_written", []))
                modifiers=_names(getattr(function, "modifiers", []))
                external_calls=[]
                for call in getattr(function, "high_level_calls", []) or []:
                    try:
                        external_calls.append(f"{call[0].name}.{call[1].name}")
                    except (AttributeError, IndexError, TypeError):
                        external_calls.append(str(call))
                for variable in getattr(function, "state_variables_read", []) or []:
                    readers[getattr(variable, "canonical_name", None) or variable.name].add(function.canonical_name)
                    state_objects[getattr(variable, "canonical_name", None) or variable.name]=variable
                for variable in getattr(function, "state_variables_written", []) or []:
                    writers[getattr(variable, "canonical_name", None) or variable.name].add(function.canonical_name)
                    state_objects[getattr(variable, "canonical_name", None) or variable.name]=variable

                is_entrypoint=visibility in {"public", "external"}
                is_mutating=mutability not in {"view", "pure"}
                row={
                    "name": function.canonical_name,
                    "source_location": _source_location(function),
                    "visibility": visibility,
                    "state_mutability": mutability,
                    "is_external_entrypoint": is_entrypoint,
                    "reads": reads,
                    "writes": writes,
                    "modifiers": modifiers,
                    "high_level_calls": sorted(set(external_calls)),
                }
                function_rows.append(row)

                if is_entrypoint and is_mutating and writes and not modifiers:
                    finding_index+=1
                    findings.append({
                        "id": f"LOGIC-{finding_index:04d}",
                        "rule_id": "LOGIC001",
                        "category": "cross_function_logic",
                        "title": "State-changing external entrypoint requires authorization-path review",
                        "description": "This public/external state-changing function writes contract storage and has no Solidity modifier. Authorization may still be enforced inside the function or in an inherited/internal call; inspect the complete path before drawing conclusions.",
                        "severity": "undetermined",
                        "confidence": "low",
                        "status": "needs_review",
                        "contract": contract.name,
                        "function": function.canonical_name,
                        "source_location": _source_location(function),
                        "state_variables_written": writes,
                        "evidence": {"visibility": visibility, "modifiers": modifiers, "writes": writes},
                        "preconditions": ["Determine whether the function is intended to be permissionless.", "Trace require/revert checks and inherited/internal authorization."],
                        "requires_manual_validation": True,
                    })

            for variable_name in sorted(set(writers) | set(readers)):
                writer_names=sorted(writers.get(variable_name, set()))
                reader_names=sorted(readers.get(variable_name, set()))
                if len(writer_names) >= 2:
                    finding_index+=1
                    variable=state_objects.get(variable_name)
                    finding={
                        "id": f"LOGIC-{finding_index:04d}",
                        "rule_id": "LOGIC002",
                        "category": "cross_function_logic",
                        "title": "Shared state variable has multiple write paths",
                        "description": "Multiple functions write the same state variable. Review whether all transitions preserve the protocol's accounting and lifecycle invariants, including alternate entrypoints and emergency paths.",
                        "severity": "undetermined",
                        "confidence": "low",
                        "status": "needs_review",
                        "contract": contract.name,
                        "state_variable": variable_name,
                        "writer_functions": writer_names,
                        "writer_locations": {row["name"]: row["source_location"] for row in function_rows if row["name"] in writer_names},
                        "reader_functions": reader_names,
                        "evidence": {"writers": writer_names, "readers": reader_names},
                        "preconditions": ["Define the invariant for this variable.", "Compare every writer's preconditions and paired state updates.", "Check whether callers can reach inconsistent orderings."],
                        "requires_manual_validation": True,
                    }
                    if variable is not None:
                        finding["state_variable_visibility"]=getattr(variable, "visibility", None)
                    findings.append(finding)

            contracts.append({
                "name": contract.name,
                "functions": function_rows,
                "state_interactions": [
                    {"variable": name, "readers": sorted(readers.get(name, set())), "writers": sorted(writers.get(name, set()))}
                    for name in sorted(set(readers) | set(writers))
                ],
            })

        return {
            "status": "completed",
            "engine": "slither-python-api",
            "contracts_analyzed": len(contracts),
            "entrypoints_analyzed": sum(1 for c in contracts for f in c["functions"] if f["is_external_entrypoint"]),
            "findings_count": len(findings),
            "contracts": contracts,
            "findings": findings,
            "limitations": [
                "These are semantic review leads, not confirmed vulnerabilities.",
                "No path feasibility, economic impact, or exploitability is established.",
                "Inline authorization and cross-contract invariants require manual call-path review and local tests.",
            ],
        }
    except Exception as exc:
        return {
            "status": "failed",
            "engine": "slither-python-api",
            "error": f"{type(exc).__name__}: {exc}"[:1000],
            "contracts": [],
            "findings": [],
        }
