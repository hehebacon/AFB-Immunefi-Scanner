import unittest
from afb_immunefi.reference_intelligence import classify_references, fetch_audit_pdfs, fetch_github_history, crawl_documentation

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


    def test_github_history_paginates_beyond_first_hundred(self):
        import tempfile, json
        from pathlib import Path
        from unittest.mock import patch
        class Response:
            def __init__(self,payload): self.payload=payload
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def geturl(self): return "https://api.github.com/repos/example/project/commits"
            def read(self,n): return json.dumps(self.payload).encode()
        first=[{"sha":str(i),"html_url":"https://github.com/example/project/commit/"+str(i),"commit":{"author":{"date":"2026-01-01","name":"dev"},"message":"commit"}} for i in range(100)]
        with tempfile.TemporaryDirectory() as tmp, patch("afb_immunefi.reference_intelligence.urlopen",side_effect=[Response(first),Response([first[0]])]) as mocked:
            result=fetch_github_history("https://github.com/example/project",Path(tmp),max_commits=150)
            self.assertEqual(result["commit_count"],101)
            self.assertEqual(result["pages_collected"],2)
            self.assertEqual(mocked.call_count,2)

    def test_documentation_crawl_is_same_host_only(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        class Response:
            status=200
            headers={"Content-Type":"text/html"}
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def geturl(self): return "https://docs.example.org/start"
            def read(self,n): return b'<html><body>Guide <a href="/next">Next</a><a href="https://evil.example/page">External</a></body></html>'
        with tempfile.TemporaryDirectory() as tmp, patch("afb_immunefi.reference_intelligence.urlopen",return_value=Response()):
            result=crawl_documentation([{"url":"https://docs.example.org/start","kind":"documentation"}],Path(tmp),max_pages=5,max_depth=1)
            self.assertEqual(result["pages_saved"],1)
            self.assertEqual(result["queue_remaining"],1)

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
