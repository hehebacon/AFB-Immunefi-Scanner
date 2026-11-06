import unittest
from unittest.mock import patch
from afb_immunefi.deployment_verification import verify_targets
from afb_immunefi.reference_intelligence import classify_references

class DeploymentVerificationTests(unittest.TestCase):
    @patch("afb_immunefi.deployment_verification.urlopen")
    def test_sourcify_exact_match_is_reported_as_metadata_only(self,mock_open):
        class Response:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): return b'{"match":"exact_match","creationMatch":"exact_match","runtimeMatch":"exact_match","compiler":{"version":"0.8.24"}}'
        mock_open.return_value=Response()
        result=verify_targets([{"chain_id":"1","address":"0x"+"a"*40,"label":"Vault"}])
        self.assertEqual(result["results"][0]["status"],"verified_match")
        self.assertTrue(result["policy"]["verified_match_is_not_scope_confirmation"])

    def test_invalid_address_is_not_requested(self):
        result=verify_targets([{"chain_id":"1","address":"not-an-address"}])
        self.assertEqual(result["results"][0]["status"],"invalid_target")

if __name__=="__main__": unittest.main()
