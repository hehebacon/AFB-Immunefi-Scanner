import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch
from afb_immunefi.logic_analysis import run_logic_review, _transitive_state_access


class LogicReviewTests(unittest.TestCase):
    def test_missing_slither_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_logic_review(Path(tmp))
            self.assertEqual(result["status"], "not_installed")
            self.assertEqual(result["findings"], [])

    def test_logic_leads_are_unverified(self):
        class Variable:
            def __init__(self, name):
                self.name = name
                self.canonical_name = name
                self.visibility = "private"

        class Function:
            def __init__(self, name, visibility, writes, reads=(), modifiers=(), mutability="nonpayable"):
                self.name = name
                self.canonical_name = "Demo." + name
                self.visibility = visibility
                self.state_mutability = mutability
                self.state_variables_read = [Variable(x) for x in reads]
                self.state_variables_written = [Variable(x) for x in writes]
                self.modifiers = [type("Modifier", (), {"name": x, "canonical_name": x})() for x in modifiers]
                self.high_level_calls = []
                self.internal_calls = []
                self.nodes = []

        class Contract:
            name = "Demo"
            functions_declared = [
                Function("deposit", "external", ["totalBalance"]),
                Function("withdraw", "external", ["totalBalance"], ["totalBalance"], ["onlyOwner"]),
            ]

        class FakeSlither:
            def __init__(self, _path, **_kwargs):
                self.contracts = [Contract()]

        with tempfile.TemporaryDirectory() as tmp:
            fake_module = types.SimpleNamespace(Slither=FakeSlither)
            with patch.dict(sys.modules, {"slither": fake_module}):
                result = run_logic_review(Path(tmp))
        self.assertEqual(result["status"], "completed")
        self.assertGreaterEqual(result["findings_count"], 1)
        self.assertTrue(all(x["status"] == "needs_review" for x in result["findings"]))
        self.assertTrue(any(x["rule_id"] == "LOGIC002" for x in result["findings"]))
        self.assertTrue(any(x["rule_id"] == "LOGIC003" for x in result["findings"]))
        self.assertGreaterEqual(result["invariant_candidates_count"], 1)
        self.assertEqual(result["analysis_capabilities"]["path_sensitive_symbolic_execution"], "not_implemented")

    def test_transitive_internal_call_state_effects_include_cycles(self):
        rows = {
            "Demo.entry": {
                "internal_calls": ["Demo._write"],
                "reads": [],
                "writes": [],
            },
            "Demo._write": {
                "internal_calls": ["Demo._leaf"],
                "reads": [],
                "writes": ["Demo.balance"],
            },
            "Demo._leaf": {
                "internal_calls": ["Demo._write"],
                "reads": ["Demo.total"],
                "writes": ["Demo.total"],
            },
        }
        reachable, reads, writes = _transitive_state_access("Demo.entry", rows)
        self.assertEqual(reachable, ["Demo._leaf", "Demo._write"])
        self.assertEqual(reads, ["Demo.total"])
        self.assertEqual(writes, ["Demo.balance", "Demo.total"])

    def test_entrypoint_inherits_state_writes_from_internal_helper(self):
        class Variable:
            def __init__(self, name):
                self.name = name
                self.canonical_name = name
                self.visibility = "private"

        class Function:
            def __init__(self, name, visibility, writes=(), internal_calls=()):
                self.name = name
                self.canonical_name = "Demo." + name
                self.visibility = visibility
                self.state_mutability = "nonpayable"
                self.state_variables_read = []
                self.state_variables_written = [Variable(x) for x in writes]
                self.modifiers = []
                self.high_level_calls = []
                self.internal_calls = [type("Called", (), {"name": x, "canonical_name": x})() for x in internal_calls]
                self.nodes = []

        class Contract:
            name = "Demo"
            functions_declared = [
                Function("deposit", "external", internal_calls=["Demo._credit"]),
                Function("_credit", "internal", writes=["Demo.balance"]),
            ]

        class FakeSlither:
            def __init__(self, _path, **_kwargs):
                self.contracts = [Contract()]

        with tempfile.TemporaryDirectory() as tmp:
            fake_module = types.SimpleNamespace(Slither=FakeSlither)
            with patch.dict(sys.modules, {"slither": fake_module}):
                result = run_logic_review(Path(tmp))

        lead = next(item for item in result["findings"] if item["rule_id"] == "LOGIC001")
        self.assertEqual(lead["function"], "Demo.deposit")
        self.assertEqual(lead["state_variables_written"], ["Demo.balance"])
        self.assertEqual(lead["reachable_internal_functions"], ["Demo._credit"])
        self.assertEqual(lead["status"], "needs_review")


if __name__ == "__main__":
    unittest.main()
