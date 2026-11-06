import unittest
from afb_immunefi.program_intake import validate_program_url, build_scope_draft

class ProgramIntakeTests(unittest.TestCase):
    def test_accepts_information_page_and_extracts_slug(self):
        slug, url = validate_program_url("https://immunefi.com/bug-bounty/ssvnetwork/information/")
        self.assertEqual(slug, "ssvnetwork")
        self.assertIn("/information/", url)

    def test_rejects_non_immunefi_host(self):
        with self.assertRaises(ValueError):
            validate_program_url("https://example.com/bug-bounty/ssvnetwork/information/")

    def test_rejects_wrong_path(self):
        with self.assertRaises(ValueError):
            validate_program_url("https://immunefi.com/bug-bounty/ssvnetwork/")

    def test_scope_draft_marks_candidates_unverified(self):
        page = {
            "slug": "sample", "requested_url": "https://immunefi.com/bug-bounty/sample/information/",
            "fetched_at": "2026-11-06T00:00:00+00:00", "sha256": "abc",
            "text": "Ethereum mainnet contract 0x0000000000000000000000000000000000000001 In-scope assets",
            "final_url": "https://immunefi.com/bug-bounty/sample/information/", "links": []
        }
        draft = build_scope_draft(page)
        self.assertEqual(draft["in_scope_assets_candidates"][0]["status"], "candidate_only")
        self.assertEqual(draft["verification_status"], "unverified_human_review_required")

if __name__ == "__main__":
    unittest.main()
