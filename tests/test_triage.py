import json
import tempfile
import unittest
from pathlib import Path

from afb_immunefi.triage import deduplicate_findings, benchmark_findings, load_echidna_report


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
