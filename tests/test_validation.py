import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from afb_immunefi.validation import run_forge_differential, run_forge_validation


class ValidationTests(unittest.TestCase):
    def test_differential_reports_changed_test_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before, after = root / "before", root / "after"
            before.mkdir(); after.mkdir()
            payloads = [
                {"test_results": [{"test": "testWithdraw", "status": "success"}]},
                {"test_results": [{"test": "testWithdraw", "status": "failure"}]},
            ]
            from types import SimpleNamespace
            with patch("afb_immunefi.validation.shutil.which", return_value="/usr/bin/forge"), patch(
                "afb_immunefi.validation.subprocess.run",
                side_effect=[
                    SimpleNamespace(returncode=0, stdout=json.dumps(payloads[0]), stderr=""),
                    SimpleNamespace(returncode=1, stdout=json.dumps(payloads[1]), stderr=""),
                ],
            ):
                result = run_forge_differential(before, after, root / "diff.json")
            self.assertEqual(len(result["changed_test_outcomes"]), 1)
            self.assertEqual(result["changed_test_outcomes"][0]["reference"], "success")
            self.assertEqual(result["changed_test_outcomes"][0]["candidate"], "failure")

    def test_validation_maps_failing_test_without_confirming_bug(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"; project.mkdir()
            mapping = root / "map.json"
            mapping.write_text(json.dumps({"finding_tests": {"LOGIC-1": "test_AFB_LOGIC_1"}}))
            from types import SimpleNamespace
            payload = {"test_results": [{"test": "test_AFB_LOGIC_1", "status": "failure"}]}
            with patch("afb_immunefi.validation.shutil.which", return_value="/usr/bin/forge"), patch(
                "afb_immunefi.validation.subprocess.run",
                return_value=SimpleNamespace(returncode=1, stdout=json.dumps(payload), stderr=""),
            ):
                result = run_forge_validation(project, mapping, root / "validation.json")
            self.assertFalse(result["all_findings_confirmed"])
            self.assertEqual(result["validations"][0]["interpretation"], "failed_test_requires_manual_reproduction_and_root_cause_review")


if __name__ == "__main__":
    unittest.main()
