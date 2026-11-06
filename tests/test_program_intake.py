import unittest
from afb_immunefi.program_intake import validate_program_url, build_scope_draft
from afb_immunefi.source_discovery import download_linked_solidity_repo

class ProgramIntakeTests(unittest.TestCase):
    def test_accepts_program_pages_and_extracts_slug(self):
        for page in ("information", "scope", "resources"):
            slug, url = validate_program_url(f"https://immunefi.com/bug-bounty/ssvnetwork/{page}/")
            self.assertEqual(slug, "ssvnetwork")
            self.assertIn(f"/{page}/", url)

    def test_rejects_non_immunefi_host(self):
        with self.assertRaises(ValueError):
            validate_program_url("https://example.com/bug-bounty/ssvnetwork/information/")

    def test_rejects_wrong_path(self):
        with self.assertRaises(ValueError):
            validate_program_url("https://immunefi.com/bug-bounty/ssvnetwork/")

    def test_source_discovery_skips_when_no_repository_link_exists(self):
        with self.subTest("no linked source repository"):
            import tempfile
            from pathlib import Path
            with tempfile.TemporaryDirectory() as tmp:
                result = download_linked_solidity_repo([], Path(tmp))
                self.assertEqual(result["status"], "no_github_repository_link")

    def test_scope_draft_only_uses_scope_tab_for_asset_candidates(self):
        address = "0x0000000000000000000000000000000000000001"
        page = {
            "slug": "sample",
            "requested_url": "https://immunefi.com/bug-bounty/sample/information/",
            "fetched_at": "2026-11-06T00:00:00+00:00",
            "sha256": "abc",
            "text": "General information",
            "final_url": "https://immunefi.com/bug-bounty/sample/information/",
            "links": [],
            "pages": [
                {
                    "final_url": "https://immunefi.com/bug-bounty/sample/information/",
                    "text": f"General information {address}",
                    "links": [f"https://etherscan.io/address/{address}"],
                    "sha256": "info"
                },
                {
                    "final_url": "https://immunefi.com/bug-bounty/sample/scope/",
                    "text": f"Assets in Scope: Ethereum mainnet contract {address}",
                    "links": [f"https://etherscan.io/address/{address}"],
                    "sha256": "scope"
                }
            ]
        }
        draft = build_scope_draft(page)
        self.assertEqual(draft["in_scope_assets_candidates"][0]["address"], address)
        self.assertEqual(draft["in_scope_assets_candidates"][0]["status"], "candidate_only")
        self.assertEqual(draft["verification_status"], "unverified_human_review_required")

    def test_information_page_alone_does_not_create_scope_candidates(self):
        address = "0x0000000000000000000000000000000000000001"
        page = {
            "slug": "sample",
            "requested_url": "https://immunefi.com/bug-bounty/sample/information/",
            "fetched_at": "2026-11-06T00:00:00+00:00",
            "sha256": "abc",
            "text": f"Assets in Scope: {address}",
            "final_url": "https://immunefi.com/bug-bounty/sample/information/",
            "links": []
        }
        draft = build_scope_draft(page)
        self.assertEqual(draft["in_scope_assets_candidates"], [])

