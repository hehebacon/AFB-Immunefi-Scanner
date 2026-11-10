"""Bounded path-condition exploration over Slither CFGs.

This is a bounded symbolic *path feasibility* pass, not full EVM symbolic execution:
it does not model storage values, external calls, gas, reentrancy or Solidity arithmetic
bit-vectors. Z3 is optional; unsupported expressions remain explicitly unknown.
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict


class _Z3Expression:
    def __init__(self, z3):
        self.z3 = z3
        self.symbols = {}

    def _symbol(self, name):
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if safe not in self.symbols:
            self.symbols[safe] = self.z3.Int(safe)
        return self.symbols[safe]

    def parse(self, expression):
        value = (expression or "").strip()
        if not value or len(value) > 500:
            raise ValueError("empty_or_oversized_expression")
        if any(token in value for token in ("(", ")", "[", "]", "?", ":", "++", "--", "=")):
            raise ValueError("unsupported_solidity_expression")
        value = value.replace("&&", " and ").replace("||", " or ")
        value = re.sub(r"(?<![=!<>])!(?!=)", " not ", value)
        value = re.sub(r"\btrue\b", "True", value, flags=re.I)
        value = re.sub(r"\bfalse\b", "False", value, flags=re.I)
        tree = ast.parse(value, mode="eval")
        return self._visit(tree.body)

    def _visit(self, node):
        z3 = self.z3
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, bool)):
            return z3.BoolVal(node.value) if isinstance(node.value, bool) else z3.IntVal(node.value)
        if isinstance(node, ast.Name):
            if node.id in {"True", "False"}:
                return z3.BoolVal(node.id == "True")
            return self._symbol(node.id)
        if isinstance(node, ast.UnaryOp):
            operand = self._visit(node.operand)
            if isinstance(node.op, ast.Not): return z3.Not(operand)
            if isinstance(node.op, ast.USub): return -operand
            if isinstance(node.op, ast.UAdd): return operand
        if isinstance(node, ast.BinOp):
            left, right = self._visit(node.left), self._visit(node.right)
            ops = {
                ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right, ast.FloorDiv: lambda: left / right,
                ast.Div: lambda: left / right, ast.Mod: lambda: left % right,
                ast.BitAnd: lambda: z3.And(left != 0, right != 0),
                ast.BitOr: lambda: z3.Or(left != 0, right != 0),
            }
            for kind, fn in ops.items():
                if isinstance(node.op, kind): return fn()
        if isinstance(node, ast.BoolOp):
            values = [self._visit(x) for x in node.values]
            return z3.And(*values) if isinstance(node.op, ast.And) else z3.Or(*values)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = self._visit(node.left), self._visit(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Eq): return left == right
            if isinstance(op, ast.NotEq): return left != right
            if isinstance(op, ast.Lt): return left < right
            if isinstance(op, ast.LtE): return left <= right
            if isinstance(op, ast.Gt): return left > right
            if isinstance(op, ast.GtE): return left >= right
        raise ValueError("unsupported_expression_node")


def _path_status(constraints, z3_module):
    if z3_module is None:
        return "unknown"
    parser = _Z3Expression(z3_module)
    solver = z3_module.Solver()
    try:
        for expression, truth in constraints:
            term = parser.parse(expression)
            if not z3_module.is_bool(term):
                term = term != 0
            solver.add(term if truth else z3_module.Not(term))
    except (SyntaxError, ValueError, TypeError, z3_module.Z3Exception):
        return "unknown"
    result = solver.check()
    return "feasible" if result == z3_module.sat else "infeasible" if result == z3_module.unsat else "unknown"


def explore_contract_paths(contract_row, *, max_paths=250, max_depth=100):
    """Explore bounded CFG paths and solve supported branch predicates with Z3."""
    try:
        import z3
    except ImportError:
        z3 = None

    by_function = defaultdict(dict)
    for node in contract_row.get("cfg_nodes", []):
        by_function[node.get("function")][node.get("node_id")] = node

    results = []
    totals = {"feasible": 0, "infeasible": 0, "unknown": 0, "truncated": 0}
    for function in contract_row.get("functions", []):
        name = function.get("name")
        graph = by_function.get(name, {})
        if not graph:
            continue
        incoming = {node_id: 0 for node_id in graph}
        for node in graph.values():
            for child in node.get("successors", []):
                if child in incoming: incoming[child] += 1
        entries = [node_id for node_id, degree in incoming.items() if degree == 0]
        if not entries:
            entries = [next(iter(graph))]
        stack = [(entry, [entry], []) for entry in entries]
        seen_paths = 0
        while stack:
            current, path, constraints = stack.pop()
            if seen_paths >= max_paths:
                totals["truncated"] += 1
                break
            node = graph.get(current)
            if node is None:
                continue
            successors = [x for x in node.get("successors", []) if x in graph]
            if not successors or len(path) >= max_depth:
                status = _path_status(constraints, z3)
                totals[status] += 1
                seen_paths += 1
                results.append({
                    "function": name, "nodes": path, "constraints": [
                        {"expression": expr, "truth": truth} for expr, truth in constraints
                    ], "feasibility": status,
                    "terminal": current, "bounded": len(path) >= max_depth,
                })
                continue
            true_id = node.get("true_successor")
            false_id = node.get("false_successor")
            expression = node.get("expression", "")
            for child in reversed(successors):
                next_constraints = list(constraints)
                if len(successors) == 2 and expression and (true_id is not None or false_id is not None):
                    if child == true_id: next_constraints.append((expression, True))
                    elif child == false_id: next_constraints.append((expression, False))
                next_path = path + [child]
                if child in path:
                    # A loop is represented as a bounded terminal path, not expanded forever.
                    status = _path_status(next_constraints, z3)
                    totals[status] += 1
                    seen_paths += 1
                    results.append({
                        "function": name, "nodes": next_path,
                        "constraints": [{"expression": e, "truth": t} for e, t in next_constraints],
                        "feasibility": status, "terminal": child, "bounded": True,
                    })
                else:
                    stack.append((child, next_path, next_constraints))
    return {
        "engine": "bounded_cfg_path_condition_solver",
        "solver": "z3" if z3 is not None else "unavailable",
        "contracts": 1,
        "paths": results,
        "summary": totals,
        "limitations": [
            "Only simple integer/boolean branch expressions are translated.",
            "This pass checks path-condition consistency; it does not symbolically execute EVM state or prove a vulnerability.",
            "Loops are cut when a node repeats and paths are bounded by max_depth/max_paths.",
            "Unsupported expressions are unknown, never assumed feasible or safe.",
        ],
    }


def infer_structural_invariants(contract_row):
    """Infer invariant *hypotheses* from co-mutated storage and arithmetic IR, not names."""
    functions = contract_row.get("functions", [])
    cfg_by_function = defaultdict(list)
    for node in contract_row.get("cfg_nodes", []):
        cfg_by_function[node.get("function")].extend(node.get("ir_details", []))
    candidates = []
    for function in functions:
        writes = sorted(set(function.get("effective_writes") or function.get("writes") or []))
        if len(writes) < 2:
            continue
        operations = sorted({
            detail.get("operation", "unknown")
            for detail in cfg_by_function.get(function.get("name"), [])
            if detail.get("operation")
        })
        arithmetic = [x for x in operations if any(k in x.lower() for k in ("binary", "assignment", "unary"))]
        candidates.append({
            "candidate_id": f"INV-{len(candidates)+1:04d}",
            "function": function.get("name"),
            "co_mutated_state_variables": writes,
            "observed_ir_operation_families": operations,
            "arithmetic_or_assignment_operations": arithmetic,
            "hypothesis": "These storage variables participate in a coupled state transition; derive a conservation or lifecycle relation from the protocol specification and validate every writer.",
            "evidence_level": "storage_dataflow_and_ir_structure",
            "status": "hypothesis_requires_oracle",
            "requires_protocol_oracle": True,
        })
    return candidates
