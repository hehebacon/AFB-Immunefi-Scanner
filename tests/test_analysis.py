import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from unittest.mock import patch
from afb_immunefi.analysis import _slither_findings, run_analysis
from afb_immunefi.cli import main

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

    def test_analyze_cli_runs_after_explicit_policy_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            workspace=root/"workspace"
            policy_dir=workspace/"program"
            policy_dir.mkdir(parents=True)
            (policy_dir/"policy.yaml").write_text(
                "program_name: Demo\nprogram_url: https://immunefi.com/bug-bounty/demo/information/\n"
                "last_checked: 2026-11-06\nscope_confirmed: true\ntesting_constraints_reviewed: true\n"
                "safe_harbor_reviewed: true\nin_scope_assets:\n  - address: '0x0000000000000000000000000000000000000001'\n",
                encoding="utf-8"
            )
            source=root/"contracts"
            source.mkdir()
            (source/"Demo.sol").write_text("pragma solidity ^0.8.20;\ncontract Demo {}\n",encoding="utf-8")
            output=root/"analysis.json"
            argv=["afb-immunefi","analyze","--source",str(source),"--workspace",str(workspace),"--output",str(output),"--no-static-tools"]
            with patch("sys.argv",argv):
                self.assertEqual(main(),0)
            data=json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["coverage"]["tools"]["slither"]["status"],"not_requested")
            self.assertEqual(data["validation_policy"]["confirmed_vulnerabilities"],0)

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
