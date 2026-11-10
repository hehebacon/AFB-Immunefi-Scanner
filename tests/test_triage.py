import json
import tempfile
import unittest
from pathlib import Path

from afb_immunefi.triage import deduplicate_findings, benchmark_findings, load_echidna_report, build_triage_report, load_slither_report


class TriageTests(unittest.TestCase):
    def test_deduplicates_only_same_source_line_and_title_across_tools(self):
        rows = [
            {"id": "S1", "analyzer": "slither", "title": "reentrancy", "source": "src/V.sol", "line": 10},
            {"id": "A1", "analyzer": "aderyn", "title": "Reentrancy", "source": "src/V.sol", "line": 10},
            {"id": "S2", "analyzer": "slither", "title": "reentrancy", "source": "src/V.sol", "line": 11},
            {"id": "A2", "analyzer": "aderyn", "title": "reentrancy", "source": None, "line": None},
        ]
        result = deduplicate_findings(rows)
        self.assertEqual(len(result), 3)
        merged = next(x for x in result if x["id"] == "S1")
        self.assertEqual(set(merged["analyzers"]), {"slither", "aderyn"})

    def test_cross_analyzer_dedup_accepts_different_titles_with_shared_tokens(self):
        rows = [
            {"id": "S1", "analyzer": "slither", "title": "reentrancy-eth", "source": "src/V.sol", "line": 10},
            {"id": "A1", "analyzer": "aderyn", "title": "Reentrancy vulnerability", "source": "src/V.sol", "line": 10},
        ]
        result = deduplicate_findings(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(set(result[0]["analyzers"]), {"slither", "aderyn"})

    def test_benchmark_confusion_matrix_on_explicit_corpus(self):
        detected = [{"rule_id": "BUG-A"}, {"rule_id": "BUG-FP"}]
        result = benchmark_findings(detected, {
            "name": "tiny-fixture",
            "positive_cases": ["BUG-A", "BUG-MISSED"],
            "negative_cases": ["BUG-FP", "CLEAN"],
        })
        self.assertEqual((result["tp"], result["fp"], result["fn"], result["tn"]), (1, 1, 1, 1))
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)

    def test_slither_paths_are_resolved_against_source_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "slither.json"
            report.write_text(json.dumps({"results": {"detectors": [{
                "check": "reentrancy-eth", "impact": "High", "confidence": "Medium",
                "elements": [{"source_mapping": {"filename_relative": "contracts/V.sol", "lines": [17]}}],
            }]}}))
            rows = load_slither_report(report, root)
        self.assertEqual(rows[0]["source"], str((root / "contracts/V.sol").resolve()))
        self.assertEqual(rows[0]["line"], 17)

    def test_build_triage_report_combines_tool_outputs_and_keeps_unverified_state(self):
        result = build_triage_report(
            slither=[{"id": "S1", "analyzer": "slither", "title": "Reentrancy", "source": "src/V.sol", "line": 8}],
            aderyn=[{"id": "A1", "analyzer": "aderyn", "title": "Reentrancy", "source": "src/V.sol", "line": 8}],
            echidna=[{"id": "E1", "analyzer": "echidna", "title": "Property falsified", "source": None, "line": None}],
            logic={"findings": [{"id": "L1", "analyzer": "afb", "title": "State invariant review", "source": "src/V.sol", "line": 22}]},
        )
        self.assertEqual(result["raw_finding_count"], 4)
        self.assertEqual(result["deduplicated_finding_count"], 3)
        self.assertEqual(result["validation_status"], "unverified_until_local_test_reproduction")

    def test_echidna_only_emits_falsified_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "echidna.json"
            path.write_text(json.dumps({"tests": {
                "echidna_conservation": {"status": "falsified", "transactions": []},
                "echidna_other": {"status": "solved"},
            }}))
            result = load_echidna_report(path)
        self.assertEqual(len(result), 1)
        self.assertIn("conservation", result[0]["title"])


if __name__ == "__main__":
    unittest.main()
