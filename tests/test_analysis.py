import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from afb_immunefi.analysis import _slither_findings, run_analysis

class AnalysisTests(unittest.TestCase):
    def test_normalizes_slither_detector_without_claiming_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/"Demo.sol"
            source.write_text("pragma solidity ^0.8.20;\ncontract Demo {}\n")
            output=root/"slither.json"
            output.write_text(json.dumps({"results":{"detectors":[{
                "check":"reentrancy-eth",
                "impact":"High",
                "confidence":"Medium",
                "description":"Potential reentrancy issue",
                "elements":[{"type":"function","name":"Demo.withdraw","source_mapping":{"filename_relative":"Demo.sol","lines":[2]}}]
            }]}}))
            findings=_slither_findings(output,root)
            self.assertEqual(len(findings),1)
            self.assertEqual(findings[0]["severity"],"high")
            self.assertEqual(findings[0]["status"],"tool_reported_unverified")
            self.assertTrue(findings[0]["requires_manual_validation"])
            self.assertEqual(findings[0]["evidence"],"contract Demo {}")

    def test_unified_analysis_reports_missing_slither_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"Demo.sol").write_text("pragma solidity ^0.8.20;\ncontract Demo { function f() external { tx.origin; } }\n")
            with patch("afb_immunefi.analysis.shutil.which",return_value=None):
                result=run_analysis(root,root/"workspace")
            self.assertEqual(result["coverage"]["solidity_files"],1)
            self.assertEqual(result["coverage"]["tools"]["slither"]["status"],"not_installed")
            self.assertEqual(result["validation_policy"]["confirmed_vulnerabilities"],0)
            self.assertTrue(all(x["status"]=="potential" for x in result["findings"] if x["category"]!="slither"))

if __name__=="__main__":
    unittest.main()
