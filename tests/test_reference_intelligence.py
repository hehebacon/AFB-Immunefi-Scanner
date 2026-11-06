import unittest
from afb_immunefi.reference_intelligence import classify_references, fetch_audit_pdfs

class ReferenceIntelligenceTests(unittest.TestCase):
    def test_classifies_resources_references(self):
        records=classify_references([
            "https://github.com/example/protocol",
            "https://example.org/audit.pdf",
            "https://docs.example.org/guide",
            "http://example.org/insecure",
            "https://127.0.0.1/private.pdf"
        ])
        kinds={item["kind"] for item in records}
        self.assertIn("github_repository",kinds)
        self.assertIn("audit_or_document_pdf",kinds)
        self.assertIn("documentation",kinds)
        self.assertEqual(len(records),3)

    def test_pdf_collection_handles_empty_reference_list(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            result=fetch_audit_pdfs([],Path(tmp))
            self.assertEqual(result["status"],"completed")
            self.assertEqual(result["candidates"],0)
            self.assertEqual(result["saved"],[])

if __name__=="__main__":
    unittest.main()
