import unittest
from afb_immunefi.brains import run_five_brains


class ParallelBrainTests(unittest.TestCase):
    def test_five_brains_run_and_return_review_hypotheses(self):
        contract = {
            "name": "Demo",
            "functions": [
                {"name": "Demo.deposit", "is_external_entrypoint": True,
                 "state_mutability": "nonpayable", "effective_writes": ["Demo.balance", "Demo.total"],
                 "writes": ["Demo.balance", "Demo.total"], "modifiers": [],
                 "high_level_calls": ["Token.transfer"], "reachable_internal_functions": []},
                {"name": "Demo.withdraw", "is_external_entrypoint": True,
                 "state_mutability": "nonpayable", "effective_writes": ["Demo.balance"],
                 "writes": ["Demo.balance"], "modifiers": ["onlyOwner"],
                 "high_level_calls": [], "reachable_internal_functions": []},
            ],
            "cfg_nodes": [{"function": "Demo.deposit", "ir_details": [
                {"operation": "Binary", "text": "balance + amount"}
            ]}],
        }
        result = run_five_brains([contract])
        self.assertEqual(result["brain_count"], 5)
        self.assertEqual(result["execution"], "parallel")
        self.assertTrue(result["all_unverified"])
        self.assertEqual(
            {item["analyzer"] for item in result["hypotheses"]},
            {"brain_auth", "brain_state", "brain_external", "brain_transition", "brain_accounting"},
        )
        self.assertTrue(all(item["status"] == "needs_review" for item in result["hypotheses"]))


if __name__ == "__main__":
    unittest.main()
