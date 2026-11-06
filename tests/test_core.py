import tempfile,unittest
from pathlib import Path
from afb_immunefi.inventory import inventory_sources
from afb_immunefi.detectors import scan_sources
from afb_immunefi.policy import policy_issues
class CoreTests(unittest.TestCase):
 def test_inventory_and_review_leads(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); (root/"Demo.sol").write_text("pragma solidity ^0.8.20;\ncontract Demo { function f() external { tx.origin; } }")
   inv=inventory_sources(root); self.assertEqual(inv[0]["contracts"],["Demo"])
   leads=scan_sources(root); self.assertTrue(any(x["rule_id"]=="SOL005" for x in leads))
   self.assertTrue(all(x["severity"]=="undetermined" for x in leads))
 def test_policy_gate_requires_confirmations(self):
  issues=policy_issues({"program_name":"Demo"})
  self.assertTrue(any("scope_confirmed" in x for x in issues))
  self.assertTrue(any("in_scope_assets" in x for x in issues))
if __name__=="__main__": unittest.main()
