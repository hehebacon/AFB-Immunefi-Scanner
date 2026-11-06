import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from afb_immunefi.toolchain import run_aderyn_local

class ToolchainTests(unittest.TestCase):
    def test_aderyn_adapter_uses_local_project_and_json_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            project=root/"project"
            project.mkdir()
            output=root/"reports"/"aderyn.json"
            with patch("afb_immunefi.toolchain.shutil.which",return_value="/usr/bin/aderyn"), \
                 patch("afb_immunefi.toolchain.subprocess.run",return_value=SimpleNamespace(returncode=0,stdout="",stderr="")) as run:
                result=run_aderyn_local(project,output)
            self.assertEqual(result["returncode"],0)
            args=run.call_args.args[0]
            self.assertIn("--skip-update-check",args)
            self.assertIn("--output",args)
            self.assertEqual(args[-1],str(project.resolve()))

if __name__=="__main__":
    unittest.main()
