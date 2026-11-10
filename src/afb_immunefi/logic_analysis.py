"""Slither-backed semantic maps and cross-function logic review leads.

This module reports review hypotheses, not confirmed vulnerabilities. It uses Slither's
parsed contract model and computes a conservative transitive closure over internal calls.
It does not perform path-sensitive symbolic execution or prove reachability.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from .symbolic import explore_contract_paths, infer_structural_invariants


def _names(items) -> list[str]:
    values = []
    for item in items or []:
        name = (
            getattr(item, "canonical_name", None)
            or getattr(item, "name", None)
            or str(item)
        )
        if name not in values:
            values.append(name)
    return sorted(values)


def _source_location(item) -> dict:
    mapping = getattr(item, "source_mapping", None)
    filename = getattr(mapping, "filename", None)
    relative = getattr(filename, "relative", None) or getattr(filename, "absolute", None)
    lines = list(getattr(mapping, "lines", []) or [])
    return {"file": relative, "lines": lines}


def _transitive_state_access(function_name: str, rows_by_name: dict[str, dict]) -> tuple[list[str], list[str], list[str]]:
    """Return reachable internal functions and their transitive state read/write sets."""
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        if name in visited or name in active or name not in rows_by_name:
            return
        active.add(name)
        for child in rows_by_name[name]["internal_calls"]:
            if child in rows_by_name:
                visit(child)
        active.remove(name)
        visited.add(name)

    visit(function_name)
    root = rows_by_name[function_name]
    reachable = sorted(visited - {function_name})
    reads = set(root["reads"])
    writes = set(root["writes"])
    for name in reachable:
        reads.update(rows_by_name[name]["reads"])
        writes.update(rows_by_name[name]["writes"])
    return reachable, sorted(reads), sorted(writes)


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
        project = Slither(str(source.resolve()), compile_force_framework="hardhat")
        contracts = []
        findings = []
        finding_index = 0

        for contract in project.contracts:
            function_rows = []
            cfg_rows = []
            writers = defaultdict(set)
            readers = defaultdict(set)
            state_objects = {}

            for function in contract.functions_declared:
                visibility = getattr(function, "visibility", "internal")
                mutability = getattr(function, "state_mutability", "nonpayable")
                reads = _names(getattr(function, "state_variables_read", []))
                writes = _names(getattr(function, "state_variables_written", []))
                modifiers = _names(getattr(function, "modifiers", []))
                external_calls = []
                for call in getattr(function, "high_level_calls", []) or []:
                    try:
                        external_calls.append(f"{call[0].name}.{call[1].name}")
                    except (AttributeError, IndexError, TypeError):
                        external_calls.append(str(call))
                internal_calls = _names(getattr(function, "internal_calls", []))

                for node in getattr(function, "nodes", []) or []:
                    node_id = getattr(node, "node_id", None)
                    irs = [type(ir).__name__ for ir in (getattr(node, "irs", []) or [])]
                    successors = [
                        getattr(child, "node_id", None)
                        for child in (getattr(node, "sons", []) or [])
                    ]
                    true_node = getattr(node, "son_true", None)
                    false_node = getattr(node, "son_false", None)
                    ir_details = []
                    for ir in (getattr(node, "irs", []) or []):
                        ir_details.append({
                            "operation": type(ir).__name__,
                            "text": str(ir)[:500],
                            "lvalue": str(getattr(ir, "lvalue", "") or "")[:200],
                            "rvalue": str(getattr(ir, "rvalue", "") or "")[:200],
                        })
                    cfg_rows.append({
                        "function": function.canonical_name,
                        "node_id": node_id,
                        "node_type": str(getattr(node, "type", "unknown")),
                        "expression": str(getattr(node, "expression", "") or "")[:500],
                        "ir_operations": irs,
                        "successors": [value for value in successors if value is not None],
                        "true_successor": getattr(true_node, "node_id", None),
                        "false_successor": getattr(false_node, "node_id", None),
                        "ir_details": ir_details,
                    })

                for variable in getattr(function, "state_variables_read", []) or []:
                    variable_name = getattr(variable, "canonical_name", None) or variable.name
                    readers[variable_name].add(function.canonical_name)
                    state_objects[variable_name] = variable
                for variable in getattr(function, "state_variables_written", []) or []:
                    variable_name = getattr(variable, "canonical_name", None) or variable.name
                    writers[variable_name].add(function.canonical_name)
                    state_objects[variable_name] = variable

                is_entrypoint = visibility in {"public", "external"}
                is_mutating = mutability not in {"view", "pure"}
                function_rows.append({
                    "name": function.canonical_name,
                    "source_location": _source_location(function),
                    "visibility": visibility,
                    "state_mutability": mutability,
                    "is_external_entrypoint": is_entrypoint,
                    "reads": reads,
                    "writes": writes,
                    "effective_reads": reads,
                    "effective_writes": writes,
                    "modifiers": modifiers,
                    "high_level_calls": sorted(set(external_calls)),
                    "internal_calls": internal_calls,
                    "reachable_internal_functions": [],
                })

            # Slither's direct state read/write lists do not necessarily describe
            # helper functions called by an external entrypoint. Compute a bounded
            # graph closure so those helper effects are visible in the review map.
            rows_by_name = {row["name"]: row for row in function_rows}
            for row in function_rows:
                reachable, effective_reads, effective_writes = _transitive_state_access(
                    row["name"], rows_by_name
                )
                row["reachable_internal_functions"] = reachable
                row["effective_reads"] = effective_reads
                row["effective_writes"] = effective_writes

            for variable_name in sorted(set(writers) | set(readers)):
                writer_names = sorted(writers.get(variable_name, set()))
                reader_names = sorted(readers.get(variable_name, set()))
                if len(writer_names) >= 2:
                    finding_index += 1
                    variable = state_objects.get(variable_name)
                    finding = {
                        "id": f"LOGIC-{finding_index:04d}",
                        "rule_id": "LOGIC002",
                        "category": "cross_function_logic",
                        "title": "Shared state variable has multiple write paths",
                        "description": "Multiple functions directly write the same state variable. Review whether all transitions preserve protocol accounting and lifecycle invariants, including alternate entrypoints and emergency paths.",
                        "severity": "undetermined",
                        "confidence": "low",
                        "status": "needs_review",
                        "contract": contract.name,
                        "state_variable": variable_name,
                        "writer_functions": writer_names,
                        "writer_locations": {
                            row["name"]: row["source_location"]
                            for row in function_rows if row["name"] in writer_names
                        },
                        "reader_functions": reader_names,
                        "evidence": {"writers": writer_names, "readers": reader_names},
                        "preconditions": [
                            "Define the invariant for this variable.",
                            "Compare every writer's preconditions and paired state updates.",
                            "Check whether callers can reach inconsistent orderings.",
                        ],
                        "requires_manual_validation": True,
                    }
                    if variable is not None:
                        finding["state_variable_visibility"] = getattr(variable, "visibility", None)
                    findings.append(finding)

            # Public/external entrypoints can mutate state through internal helpers,
            # even if the entrypoint itself has no direct storage-write IR.
            for row in function_rows:
                if (
                    row["is_external_entrypoint"]
                    and row["state_mutability"] not in {"view", "pure"}
                    and row["effective_writes"]
                    and not row["modifiers"]
                ):
                    finding_index += 1
                    findings.append({
                        "id": f"LOGIC-{finding_index:04d}",
                        "rule_id": "LOGIC001",
                        "category": "cross_function_logic",
                        "title": "State-changing external entrypoint requires authorization-path review",
                        "description": "This public/external state-changing function writes contract storage directly or through an internal helper and has no Solidity modifier. Authorization may still be enforced inline, in an inherited modifier, or in a called function; inspect the complete path before drawing conclusions.",
                        "severity": "undetermined",
                        "confidence": "low",
                        "status": "needs_review",
                        "contract": contract.name,
                        "function": row["name"],
                        "source_location": row["source_location"],
                        "state_variables_written": row["effective_writes"],
                        "reachable_internal_functions": row["reachable_internal_functions"],
                        "evidence": {
                            "visibility": row["visibility"],
                            "modifiers": row["modifiers"],
                            "direct_writes": row["writes"],
                            "transitive_writes": row["effective_writes"],
                        },
                        "preconditions": [
                            "Determine whether the function is intended to be permissionless.",
                            "Trace require/revert checks and inherited/internal authorization.",
                            "Inspect every reachable helper before deciding whether a guard is missing.",
                        ],
                        "requires_manual_validation": True,
                    })

            # Different modifier sets on writers of the same state variable can
            # expose inconsistent authorization paths. This is only a review lead.
            for variable_name, writer_set in sorted(writers.items()):
                writer_rows = [row for row in function_rows if row["name"] in writer_set]
                modifier_sets = {tuple(row["modifiers"]) for row in writer_rows}
                if (
                    len(writer_rows) >= 2
                    and len(modifier_sets) > 1
                    and any(not row["modifiers"] for row in writer_rows)
                ):
                    finding_index += 1
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

            invariant_candidates = []
            for variable_name in sorted(set(writers) | set(readers)):
                lowered = variable_name.lower()
                tokens = (
                    "balance", "deposit", "withdraw", "fee", "reward", "earning",
                    "supply", "stake", "nonce", "validator", "cluster", "index",
                    "count", "total",
                )
                if any(token in lowered for token in tokens):
                    writer_names = sorted(writers.get(variable_name, set()))
                    reader_names = sorted(readers.get(variable_name, set()))
                    if writer_names:
                        invariant_candidates.append({
                            "variable": variable_name,
                            "candidate_family": "accounting_or_lifecycle",
                            "writer_functions": writer_names,
                            "reader_functions": reader_names,
                            "suggested_properties": [
                                "Every state transition preserves the protocol-specific accounting equation.",
                                "A completed withdrawal or claim cannot exceed the caller's accrued/recorded entitlement.",
                                "Lifecycle transitions preserve valid active/liquidated/migrated state relationships.",
                            ],
                            "evidence_level": "name_and_dataflow_heuristic",
                            "requires_protocol_specification": True,
                            "requires_human_authored_or_reviewed_oracle": True,
                        })

            contract_row = {
                "name": contract.name,
                "functions": function_rows,
                "cfg_nodes": cfg_rows,
                "call_graph": [
                    {"caller": row["name"], "callees": row["internal_calls"]}
                    for row in function_rows if row["internal_calls"]
                ],
                "invariant_candidates": invariant_candidates,
                "state_interactions": [
                    {
                        "variable": name,
                        "readers": sorted(readers.get(name, set())),
                        "writers": sorted(writers.get(name, set())),
                    }
                    for name in sorted(set(readers) | set(writers))
                ],
            }
            contract_row["structural_invariant_hypotheses"] = infer_structural_invariants(contract_row)
            contract_row["bounded_path_analysis"] = explore_contract_paths(contract_row)
            contracts.append(contract_row)

        path_summary = {"feasible": 0, "infeasible": 0, "unknown": 0, "truncated": 0}
        for contract_row in contracts:
            for key, value in contract_row["bounded_path_analysis"]["summary"].items():
                path_summary[key] += value

        return {
            "status": "completed",
            "engine": "slither-python-api",
            "contracts_analyzed": len(contracts),
            "entrypoints_analyzed": sum(
                1 for contract_row in contracts
                for function_row in contract_row["functions"]
                if function_row["is_external_entrypoint"]
            ),
            "findings_count": len(findings),
            "cfg_nodes_analyzed": sum(len(contract_row["cfg_nodes"]) for contract_row in contracts),
            "invariant_candidates_count": sum(
                len(contract_row["invariant_candidates"]) + len(contract_row["structural_invariant_hypotheses"])
                for contract_row in contracts
            ),
            "path_analysis_summary": path_summary,
            "analysis_capabilities": {
                "cross_function_call_and_state_map": "implemented",
                "transitive_internal_call_state_effects": "implemented_conservative_graph_closure",
                "cfg_and_ir_summary": "implemented",
                "invariant_candidate_inference": "heuristic_review_only",
                "bounded_path_condition_feasibility": "implemented_with_optional_z3",
                "path_sensitive_evm_state_symbolic_execution": "not_implemented",
                "structural_invariant_hypothesis_inference": "implemented_review_only",
                "stateful_fuzz_execution": "not_implemented_by_this_module",
                "differential_execution": "not_implemented_by_this_module",
            },
            "contracts": contracts,
            "findings": findings,
            "limitations": [
                "These are semantic review leads, not confirmed vulnerabilities.",
                "No path feasibility, economic impact, or exploitability is established.",
                "Bounded path-condition solving checks only supported branch predicates; it is not full EVM symbolic execution and does not model storage, external calls, gas or reentrancy.",
                "Internal-call state effects are a graph closure over Slither's reported calls; dynamic dispatch, library semantics and path conditions are not proven.",
                "Invariant candidates include name/dataflow heuristics and co-mutated-storage/IR hypotheses; neither is a proven protocol invariant without a reviewed oracle.",
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
