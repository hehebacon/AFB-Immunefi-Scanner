"""Unified local analysis: heuristics, Slither detectors and semantic logic review."""
from __future__ import annotations
from pathlib import Path
import json
import shutil
import subprocess
from .inventory import inventory_sources
from .detectors import scan_sources
from .toolchain import run_slither_local, run_aderyn_local
from .logic_analysis import run_logic_review
from .triage import load_aderyn_report, load_echidna_report, build_triage_report


def _severity(value: str | None) -> str:
    normalized=(value or "").strip().lower()
    return {"informational":"info","info":"info","low":"low","medium":"medium","high":"high","critical":"critical"}.get(normalized,"undetermined")


def _slither_findings(path: Path, source_root: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        payload=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):
        return []
    detectors=payload.get("results",{}).get("detectors",[])
    findings=[]
    for index,item in enumerate(detectors,1):
        elements=item.get("elements") or [{}]
        for element in elements:
            mapping=element.get("source_mapping") or {}
            filename=mapping.get("filename_relative") or mapping.get("filename_absolute") or "unknown"
            lines=mapping.get("lines") or []
            line=lines[0] if lines else None
            source_path=Path(filename)
            if not source_path.is_absolute():
                source_path=source_root/source_path
            evidence=""
            if line and source_path.is_file():
                try:
                    source_lines=source_path.read_text(encoding="utf-8",errors="replace").splitlines()
                    if 1 <= int(line) <= len(source_lines):
                        evidence=source_lines[int(line)-1].strip()[:500]
                except (OSError,ValueError):
                    pass
            findings.append({
                "id":f"SLITHER-{index:04d}-{len(findings)+1:02d}",
                "analyzer":"slither",
                "rule_id":item.get("check","slither-detector"),
                "category":"slither",
                "title":item.get("check","Slither detector reported a finding"),
                "description":item.get("description","").strip()[:4000],
                "severity":_severity(item.get("impact")),
                "confidence":(item.get("confidence") or "unknown").lower(),
                "status":"tool_reported_unverified",
                "source":str(source_path),
                "line":line,
                "evidence":evidence,
                "element_type":element.get("type"),
                "requires_manual_validation":True,
                "validation_note":"A static analyzer report is not proof of exploitability or program eligibility."
            })
    return findings


def run_analysis(source: Path, workspace: Path, include_static_tools: bool = True) -> dict:
    if not source.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source}")
    inventory=inventory_sources(source)
    heuristic=scan_sources(source)
    slither_result={"status":"not_requested"}
    aderyn_result={"status":"not_requested"}
    aderyn_findings=[]
    echidna_findings=[]
    logic_result={"status":"not_requested"}
    slither_findings=[]
    logic_findings=[]
    static_dir=workspace/"analysis"/"static"
    static_dir.mkdir(parents=True,exist_ok=True)
    slither_output=static_dir/"slither.json"
    logic_output=workspace/"analysis"/"logic-review.json"

    if include_static_tools:
        # Run semantic logic review independently: the Slither CLI executable and
        # its Python API can be installed/configured separately.
        try:
            logic_result=run_logic_review(source)
            logic_output.parent.mkdir(parents=True,exist_ok=True)
            logic_output.write_text(json.dumps(logic_result,indent=2),encoding="utf-8")
            logic_findings=logic_result.get("findings",[])
            logic_result={k:v for k,v in logic_result.items() if k!="contracts"}
            logic_result["output"]=str(logic_output)
        except (OSError,TimeoutError,ValueError,subprocess.TimeoutExpired) as exc:
            logic_result={"status":"failed","error":str(exc)}

        if shutil.which("aderyn"):
            try:
                aderyn_output=static_dir/"aderyn-report.md"
                aderyn_run=run_aderyn_local(source,aderyn_output)
                aderyn_findings=load_aderyn_report(aderyn_output) if aderyn_run["output_exists"] else []
                aderyn_result={"status":"completed" if aderyn_run["output_exists"] else "completed_without_report","returncode":aderyn_run["returncode"],"output":str(aderyn_output),"normalized_findings":len(aderyn_findings),"note":"Native report preserved; parsed findings remain unverified."}
            except (OSError,TimeoutError,ValueError,subprocess.TimeoutExpired) as exc:
                aderyn_result={"status":"failed","error":str(exc)}
        else:
            aderyn_result={"status":"not_installed","note":"Install Aderyn to enable this analysis layer."}

        if shutil.which("slither"):
            try:
                raw_result=run_slither_local(source,slither_output)
                slither_findings=_slither_findings(slither_output,source)
                slither_result={
                    "status":"completed" if slither_output.is_file() else "completed_without_json",
                    "returncode":raw_result.get("returncode"),
                    "output":str(slither_output),
                    "normalized_findings":len(slither_findings),
                    "stdout":raw_result.get("stdout",""),
                    "stderr":raw_result.get("stderr",""),
                    "note":"A non-zero exit code may still accompany a valid JSON report. Inspect stderr and report status."
                }
            except (OSError,TimeoutError,ValueError,subprocess.TimeoutExpired) as exc:
                slither_result={"status":"failed","error":str(exc)}
        else:
            slither_result={"status":"not_installed","note":"Install the Slither CLI to enable standard detector analysis."}

    echidna_path=static_dir/"echidna.json"
    if echidna_path.is_file():
        try:
            echidna_findings=load_echidna_report(echidna_path)
        except (OSError,ValueError,json.JSONDecodeError):
            echidna_findings=[]
    combined=build_triage_report(logic=[*heuristic,*logic_findings],slither=slither_findings,aderyn=aderyn_findings,echidna=echidna_findings)
    findings=combined["findings"]
    return {
        "schema_version":2,
        "analysis_mode":"local_source_analysis",
        "source_root":str(source.resolve()),
        "coverage":{
            "solidity_files":len(inventory),
            "heuristic_leads":len(heuristic),
            "slither_findings":len(slither_findings),
            "logic_review_leads":len(logic_findings),
            "aderyn_findings":len(aderyn_findings),
            "echidna_counterexamples":len(echidna_findings),
            "raw_findings_before_deduplication":combined["raw_finding_count"],
            "deduplicated_findings":combined["deduplicated_finding_count"],
            "tools":{"heuristics":"completed","slither":slither_result,"aderyn":aderyn_result,"logic_review":logic_result},
        },
        "findings":findings,
        "triage": {"raw_finding_count":combined["raw_finding_count"],"deduplicated_finding_count":combined["deduplicated_finding_count"],"validation_status":combined["validation_status"]},
        "validation_policy":{
            "confirmed_vulnerabilities":0,
            "all_results_are_unverified":True,
            "requirements":["reproduce with a local unit/fork test","confirm root cause and reachable preconditions","check deployed-source correspondence","check current program scope and exclusions","justify impact using program definitions","human review before external reporting"]
        }
    }
