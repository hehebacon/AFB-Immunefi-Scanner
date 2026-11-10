"""Command-line interface for AFB Immunefi Scanner."""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from .workspace import initialize_workspace, workspace_status
from .policy import require_policy, load_policy, policy_issues
from .inventory import inventory_sources
from .detectors import scan_sources
from .toolchain import check_tools, run_slither_local, run_echidna_local
from .reporting import write_report
from .program_intake import save_program_intake
from .analysis import run_analysis
from .deployment_verification import verify_targets_file
from .validation import run_forge_validation, run_forge_differential
from .triage import benchmark_findings

def build_parser():
    p=argparse.ArgumentParser(prog="afb-immunefi",description="Scope-first local smart-contract research assistant.")
    sub=p.add_subparsers(dest="command",required=True)
    for name,help_text in [("init","Create a research workspace."),("status","Show workspace readiness."),("policy-check","Validate human-confirmed program policy.")]:
        q=sub.add_parser(name,help=help_text); q.add_argument("--workspace",type=Path,default=Path("./workspace"))
    q=sub.add_parser("program-url",help="Fetch an official Immunefi program page and draft an evidence-based scope report."); q.add_argument("--url",required=True); q.add_argument("--workspace",type=Path,default=Path("./workspace")); q.add_argument("--max-commits",type=int,default=1000,help="Maximum number of commits to collect (1-5000)")
    q=sub.add_parser("inventory",help="Inventory local Solidity source files."); q.add_argument("--source",type=Path,required=True); q.add_argument("--output",type=Path,required=True)
    q=sub.add_parser("analyze",help="Run unified local analysis with heuristics and optional Slither."); q.add_argument("--source",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--workspace",type=Path,default=Path("./workspace")); q.add_argument("--no-static-tools",action="store_true")
    q=sub.add_parser("scan",help="Run conservative local source-review heuristics."); q.add_argument("--source",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--workspace",type=Path,default=Path("./workspace"))
    sub.add_parser("tools",help="Check local security-tool availability.")
    q=sub.add_parser("slither",help="Run Slither on local source after policy gate."); q.add_argument("--source",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--workspace",type=Path,default=Path("./workspace"))
    q=sub.add_parser("echidna",help="Run local Echidna property fuzzing against a harness after policy gate."); q.add_argument("--source",type=Path,required=True); q.add_argument("--contract",required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--config",type=Path); q.add_argument("--test-limit",type=int,default=5000); q.add_argument("--seq-len",type=int,default=50); q.add_argument("--timeout",type=int,default=1800); q.add_argument("--workspace",type=Path,default=Path("./workspace"))
    q=sub.add_parser("verify-deployments",help="Check deployed source verification metadata via read-only Sourcify API."); q.add_argument("--targets",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--workspace",type=Path,default=Path("./workspace")); q.add_argument("--source",type=Path,help="Local downloaded Solidity source tree to compare against verified source")
    q=sub.add_parser("validate",help="Run mapped local Foundry tests for review leads."); q.add_argument("--source",type=Path,required=True); q.add_argument("--test-map",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--timeout",type=int,default=1800); q.add_argument("--workspace",type=Path,default=Path("./workspace"))
    q=sub.add_parser("differential",help="Compare local Foundry test outcomes between two source snapshots."); q.add_argument("--reference",type=Path,required=True); q.add_argument("--candidate",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--timeout",type=int,default=1800); q.add_argument("--workspace",type=Path,default=Path("./workspace"))
    q=sub.add_parser("benchmark",help="Compute TP/FP/FN/TN on an explicit labeled benchmark corpus."); q.add_argument("--findings",type=Path,required=True); q.add_argument("--manifest",type=Path,required=True); q.add_argument("--output",type=Path,required=True)
    q=sub.add_parser("report",help="Generate a Markdown review report."); q.add_argument("--findings",type=Path,required=True); q.add_argument("--output",type=Path,required=True); q.add_argument("--program",default="Unspecified program")
    return p

def main():
    a=build_parser().parse_args()
    try:
        if a.command=="init":
            created=initialize_workspace(a.workspace); print(f"Workspace initialized: {a.workspace.resolve()}")
            for item in created: print(f"  + {item}")
        elif a.command=="status": print(json.dumps(workspace_status(a.workspace),indent=2))
        elif a.command=="policy-check":
            policy=load_policy(a.workspace/"program/policy.yaml"); issues=policy_issues(policy)
            print(json.dumps({"valid":not issues,"issues":issues},indent=2)); return 0 if not issues else 2
        elif a.command=="program-url":
            result=save_program_intake(a.url,a.workspace,max_commits=a.max_commits); print(json.dumps(result,indent=2))
        elif a.command=="inventory":
            records=inventory_sources(a.source); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"source_root":str(a.source.resolve()),"files":records},indent=2),encoding="utf-8"); print(f"Inventoried {len(records)} Solidity files -> {a.output}")
        elif a.command=="analyze":
            require_policy(a.workspace/"program/policy.yaml")
            result=run_analysis(a.source,a.workspace,include_static_tools=not a.no_static_tools)
            a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps({"output":str(a.output),"coverage":result["coverage"],"potential_findings":len(result["findings"]),"confirmed_vulnerabilities":0},indent=2))
        elif a.command=="scan":
            require_policy(a.workspace/"program/policy.yaml")
            records=scan_sources(a.source); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"schema_version":1,"findings":records},indent=2),encoding="utf-8"); print(f"Potential review leads: {len(records)} -> {a.output}")
        elif a.command=="tools": print(json.dumps(check_tools(),indent=2))
        elif a.command=="slither":
            require_policy(a.workspace/"program/policy.yaml")
            result=run_slither_local(a.source,a.output); print(json.dumps(result,indent=2)); return int(result["returncode"])
        elif a.command=="echidna":
            require_policy(a.workspace/"program/policy.yaml")
            result=run_echidna_local(a.source,a.contract,a.output,config=a.config,test_limit=a.test_limit,seq_len=a.seq_len,timeout=a.timeout)
            print(json.dumps({k:v for k,v in result.items() if k not in {"stdout","stderr"}},indent=2))
            return int(result["returncode"])
        elif a.command=="verify-deployments":
            require_policy(a.workspace/"program/policy.yaml")
            result=verify_targets_file(a.targets,a.output,source_root=a.source)
            print(json.dumps({"output":str(a.output),"checked":len(result["results"]),"verified_matches":sum(x.get("status")=="verified_match" for x in result["results"])},indent=2))
        elif a.command=="validate":
            require_policy(a.workspace/"program/policy.yaml")
            result=run_forge_validation(a.source,a.test_map,a.output,timeout=a.timeout)
            print(json.dumps(result,indent=2)); return 0 if result["forge_returncode"]==0 else 1
        elif a.command=="differential":
            require_policy(a.workspace/"program/policy.yaml")
            result=run_forge_differential(a.reference,a.candidate,a.output,timeout=a.timeout)
            print(json.dumps(result,indent=2)); return 0 if result["reference_returncode"]==0 and result["candidate_returncode"]==0 else 1
        elif a.command=="benchmark":
            data=json.loads(a.findings.read_text(encoding="utf-8"))
            manifest=json.loads(a.manifest.read_text(encoding="utf-8"))
            result=benchmark_findings(data.get("findings",[]),manifest)
            a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps(result,indent=2))
        elif a.command=="report":
            print(f"Report written: {write_report(a.findings,a.output,a.program)}")
        return 0
    except (OSError,ValueError,PermissionError,TimeoutError,RuntimeError,subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}"); return 2

if __name__=="__main__": raise SystemExit(main())
