"""Workspace creation and readiness checks."""
import json
from pathlib import Path
DIRECTORIES=("program","reconnaissance/sources","reconnaissance/docs","analysis/static","analysis/review-notes","findings","verification/local-tests","reports")
DEFAULT_POLICY="""# Fill from the selected program's official rules. Human confirmation required.
program_name: ""
program_url: ""
last_checked: ""
scope_confirmed: false
testing_constraints_reviewed: false
safe_harbor_reviewed: false
in_scope_assets: []
out_of_scope_assets: []
excluded_vulnerability_classes: []
required_impacts: []
notes: []
"""
DEFAULT_SCOPE="""# Only assets explicitly listed as in-scope by the program.
assets: []
"""
DEFAULT_FINDINGS={"schema_version":1,"findings":[]}
def initialize_workspace(root:Path):
    root.mkdir(parents=True,exist_ok=True); created=[]
    for relative in DIRECTORIES:
        path=root/relative
        if not path.exists(): path.mkdir(parents=True); created.append(relative+"/")
    templates={"program/policy.yaml":DEFAULT_POLICY,"program/scope.yaml":DEFAULT_SCOPE,"findings/findings.json":json.dumps(DEFAULT_FINDINGS,indent=2)+"\n"}
    for relative,content in templates.items():
        path=root/relative
        if not path.exists(): path.write_text(content,encoding="utf-8"); created.append(relative)
    return created
def workspace_status(root:Path):
    required=("program/policy.yaml","program/scope.yaml","findings/findings.json","reconnaissance/sources","analysis/static","verification/local-tests")
    checks={item:(root/item).exists() for item in required}
    policy_path=root/"program/policy.yaml"; policy_completed=False
    if policy_path.exists():
        text=policy_path.read_text(encoding="utf-8")
        policy_completed=all(x in text for x in ("scope_confirmed: true","testing_constraints_reviewed: true","safe_harbor_reviewed: true")) and 'program_name: ""' not in text and 'program_url: ""' not in text
    return {"workspace":str(root.resolve()),"exists":root.exists(),"ready":all(checks.values()),"policy_completed":policy_completed,"checks":checks}
