import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from afb_immunefi.logic_analysis import run_logic_review


class LogicReviewTests(unittest.TestCase):
    def test_missing_slither_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_logic_review(Path(tmp))
            self.assertEqual(result["status"],"not_installed")
            self.assertEqual(result["findings"],[])

    def test_logic_leads_are_unverified(self):
        class Variable:
            def __init__(self,name):
                self.name=name
                self.canonical_name=name
                self.visibility="private"

        class Function:
            def __init__(self,name,visibility,writes,reads=(),modifiers=(),mutability="nonpayable"):
                self.name=name
                self.canonical_name="Demo."+name
                self.visibility=visibility
                self.state_mutability=mutability
                self.state_variables_read=[Variable(x) for x in reads]
                self.state_variables_written=[Variable(x) for x in writes]
                self.modifiers=[type("Modifier",(),{"name":x,"canonical_name":x})() for x in modifiers]
                self.high_level_calls=[]

        class Contract:
            name="Demo"
            functions_declared=[
                Function("deposit","external",["totalBalance"]),
                Function("withdraw","external",["totalBalance"],["totalBalance"]),
            ]

        class FakeSlither:
            def __init__(self,_path):
                self.contracts=[Contract()]

        with tempfile.TemporaryDirectory() as tmp:
            with patch("slither.Slither",FakeSlither,create=True):
                result=run_logic_review(Path(tmp))
        self.assertEqual(result["status"],"completed")
        self.assertGreaterEqual(result["findings_count"],1)
        self.assertTrue(all(x["status"]=="needs_review" for x in result["findings"]))
        self.assertTrue(any(x["rule_id"]=="LOGIC002" for x in result["findings"]))


if __name__=="__main__":
    unittest.main()
