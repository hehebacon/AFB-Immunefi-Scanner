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
            cfg_rows=[]
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
                internal_calls=_names(getattr(function, "internal_calls", []))
                for node in getattr(function, "nodes", []) or []:
                    node_id=getattr(node, "node_id", None)
                    irs=[type(ir).__name__ for ir in (getattr(node, "irs", []) or [])]
                    successors=[getattr(child, "node_id", None) for child in (getattr(node, "sons", []) or [])]
                    cfg_rows.append({
                        "function": function.canonical_name,
                        "node_id": node_id,
                        "node_type": str(getattr(node, "type", "unknown")),
                        "expression": str(getattr(node, "expression", "") or "")[:500],
                        "ir_operations": irs,
                        "successors": [x for x in successors if x is not None],
                    })
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
                    "internal_calls": internal_calls,
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

            # Different modifier sets on writers of the same state variable
            # can expose inconsistent authorization paths. This is only a review lead:
            # inline checks and inherited/internal guards are not fully inferred here.
            for variable_name, writer_set in sorted(writers.items()):
                writer_rows=[row for row in function_rows if row["name"] in writer_set]
                modifier_sets={tuple(row["modifiers"]) for row in writer_rows}
                if len(writer_rows) >= 2 and len(modifier_sets) > 1 and any(not row["modifiers"] for row in writer_rows):
                    finding_index+=1
                    findings.append({
                        "id": f"LOGIC-{finding_index:04d}",
                        "rule_id": "LOGIC003",
                        "category": "cross_function_logic",
                        "title": "Shared-state writers have asymmetric modifier coverage",
                        "description": "Functions writing the same state variable use different Solidity modifier sets, and at least one writer has no modifier. Review whether all state transitions enforce equivalent authorization and lifecycle preconditions; inline and inherited checks may still make the paths safe.",
                        "severity": "undetermined",
                        "confidence": "low",
                        "status": "needs_review",
                        "contract": contract.name,
                        "state_variable": variable_name,
                        "writer_functions": sorted(writer_set),
                        "modifier_sets": {row["name"]: row["modifiers"] for row in writer_rows},
                        "source_locations": {row["name"]: row["source_location"] for row in writer_rows},
                        "requires_manual_validation": True,
                    })

            invariant_candidates=[]
            for variable_name in sorted(set(writers) | set(readers)):
                lowered=variable_name.lower()
                tokens=("balance","deposit","withdraw","fee","reward","earning","supply","stake","nonce","validator","cluster","index","count","total")
                if any(token in lowered for token in tokens):
                    writer_names=sorted(writers.get(variable_name,set()))
                    reader_names=sorted(readers.get(variable_name,set()))
                    if writer_names:
                        invariant_candidates.append({
                            "variable": variable_name,
                            "candidate_family": "accounting_or_lifecycle",
                            "writer_functions": writer_names,
                            "reader_functions": reader_names,
                            "suggested_properties": [
                                "Every state transition preserves the protocol-specific accounting equation.",
                                "A completed withdrawal or claim cannot exceed the caller's accrued/recorded entitlement.",
                                "Lifecycle transitions preserve valid active/liquidated/migrated state relationships."
                            ],
                            "evidence_level": "name_and_dataflow_heuristic",
                            "requires_protocol_specification": True,
                            "requires_human_authored_or_reviewed_oracle": True
                        })

            contracts.append({
                "name": contract.name,
                "functions": function_rows,
                "cfg_nodes": [row for row in cfg_rows if any(f["name"]==row["function"] for f in function_rows)],
                "invariant_candidates": invariant_candidates,
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
            "cfg_nodes_analyzed": len(cfg_rows),
            "invariant_candidates_count": sum(len(c["invariant_candidates"]) for c in contracts),
            "analysis_capabilities": {
                "cross_function_call_and_state_map": "implemented",
                "cfg_and_ir_summary": "implemented",
                "invariant_candidate_inference": "heuristic_review_only",
                "path_sensitive_symbolic_execution": "not_implemented",
                "stateful_fuzz_execution": "not_implemented_by_this_module",
                "differential_execution": "not_implemented_by_this_module"
            },
            "contracts": contracts,
            "findings": findings,
            "limitations": [
                "These are semantic review leads, not confirmed vulnerabilities.",
                "No path feasibility, economic impact, or exploitability is established.",
                "CFG/IR summaries are structural evidence, not path-sensitive symbolic execution.",
                "Invariant candidates are inferred from variable names and dataflow; they are not proven protocol invariants.",
                "Stateful fuzzing and differential execution require a project-specific harness and are not performed by this module.",
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
