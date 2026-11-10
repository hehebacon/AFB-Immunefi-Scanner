"""Five parallel, source-local review perspectives for smart-contract logic.

These brains emit hypotheses only. They do not prove exploitability or label zero-days.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256


def _lead(brain, contract, title, description, functions, evidence):
    names = sorted(set(functions))
    digest = sha256((brain + contract + title + "|".join(names)).encode()).hexdigest()[:12]
    return {
        "id": f"BRAIN-{brain.upper()}-{digest}",
        "analyzer": f"brain_{brain}",
        "category": "logic_review_hypothesis",
        "title": title,
        "description": description,
        "contract": contract,
        "functions": names,
        "evidence": evidence,
        "status": "needs_review",
        "confidence": "low",
        "severity": "undetermined",
        "requires_manual_validation": True,
        "validation_note": "A review hypothesis only; reproduce against a local test/fork before classifying.",
    }


def _auth(contract):
    rows = [f for f in contract.get("functions", [])
            if f.get("is_external_entrypoint")
            and f.get("state_mutability") not in {"view", "pure"}
            and f.get("effective_writes")
            and not f.get("modifiers")]
    return [_lead("auth", contract.get("name", "unknown"),
                  "External state transition needs authorization-path review",
                  "A state-changing external entrypoint reaches storage writes without a Solidity modifier. Inline, inherited, or helper authorization may still protect it.",
                  [f["name"] for f in rows],
                  {"entrypoints": [{"name": f["name"], "writes": f.get("effective_writes", []),
                                    "helpers": f.get("reachable_internal_functions", [])} for f in rows]})] if rows else []


def _state_fanout(contract):
    writers = {}
    for f in contract.get("functions", []):
        for state in f.get("effective_writes", []):
            writers.setdefault(state, []).append(f["name"])
    leads = []
    for state, names in writers.items():
        if len(set(names)) > 1:
            leads.append(_lead("state", contract.get("name", "unknown"),
                "Storage variable has multiple reachable writers",
                "Multiple functions can write the same storage variable. Compare all transitions against accounting and lifecycle properties.",
                names, {"state_variable": state, "writer_functions": sorted(set(names))}))
    return leads


def _external_interaction(contract):
    leads = []
    for f in contract.get("functions", []):
        if f.get("high_level_calls") and f.get("effective_writes"):
            leads.append(_lead("external", contract.get("name", "unknown"),
                "External interaction overlaps a state-changing function",
                "This function both performs a high-level external call and changes storage. Inspect call ordering, effects-before-interactions, callback reachability, and any reentrancy protection.",
                [f["name"]], {"external_calls": f["high_level_calls"],
                              "storage_writes": f["effective_writes"],
                              "modifiers": f.get("modifiers", [])}))
    return leads


def _transition_asymmetry(contract):
    rows = [f for f in contract.get("functions", [])
            if f.get("is_external_entrypoint")
            and f.get("state_mutability") not in {"view", "pure"}
            and f.get("effective_writes")]
    leads = []
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            shared = sorted(set(left.get("effective_writes", [])) & set(right.get("effective_writes", [])))
            if shared and set(left.get("modifiers", [])) != set(right.get("modifiers", [])):
                leads.append(_lead("transition", contract.get("name", "unknown"),
                    "Related state transitions have different guard sets",
                    "Two external entrypoints write overlapping storage but expose different Solidity modifier sets. Inline checks may make them equivalent; compare their full preconditions.",
                    [left["name"], right["name"]],
                    {"shared_state": shared, "left_modifiers": left.get("modifiers", []),
                     "right_modifiers": right.get("modifiers", [])}))
    return leads


def _accounting_shape(contract):
    leads = []
    for f in contract.get("functions", []):
        writes = sorted(set(f.get("effective_writes", [])))
        ir = [item for node in contract.get("cfg_nodes", [])
              if node.get("function") == f.get("name")
              for item in node.get("ir_details", [])]
        arithmetic = [item for item in ir
                      if any(word in item.get("operation", "").lower()
                             for word in ("binary", "unary", "assignment"))]
        if len(writes) >= 2 and arithmetic:
            leads.append(_lead("accounting", contract.get("name", "unknown"),
                "Coupled storage updates need an accounting invariant",
                "A function mutates multiple storage variables and contains arithmetic/assignment IR. Derive a specification-backed conservation or lifecycle property and test it across call sequences.",
                [f["name"]], {"storage_writes": writes,
                              "arithmetic_ir": arithmetic[:20]}))
    return leads


def run_five_brains(contracts, max_workers=5):
    """Run five independent review perspectives concurrently over parsed local facts."""
    brains = (_auth, _state_fanout, _external_interaction,
              _transition_asymmetry, _accounting_shape)
    leads = []
    with ThreadPoolExecutor(max_workers=min(max_workers, 5)) as pool:
        futures = [pool.submit(brain, contract)
                   for contract in contracts for brain in brains]
        for future in futures:
            leads.extend(future.result())
    return {
        "brain_count": 5,
        "execution": "parallel",
        "scope": "parsed_local_source_only",
        "hypotheses": leads,
        "hypothesis_count": len(leads),
        "all_unverified": True,
    }
