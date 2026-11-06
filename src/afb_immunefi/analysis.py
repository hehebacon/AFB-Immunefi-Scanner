"""Unified local analysis: heuristic leads plus optional Slither JSON findings."""
from __future__ import annotations
from pathlib import Path
import json
import shutil
from .inventory import inventory_sources
from .detectors import scan_sources
from .toolchain import run_slither_local

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

def run_analysis(source: Path, workspace: Path, include_slither: bool = True) -> dict:
    if not source.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {source}")
    inventory=inventory_sources(source)
    heuristic=scan_sources(source)
    slither_result={"status":"not_requested"}
    slither_findings=[]
    static_dir=workspace/"analysis"/"static"
    static_dir.mkdir(parents=True,exist_ok=True)
    slither_output=static_dir/"slither.json"
    if include_slither:
        if shutil.which("slither"):
            try:
                slither_result=run_slither_local(source,slither_output)
                slither_findings=_slither_findings(slither_output,source)
                slither_result={
                    "status":"completed" if slither_output.is_file() else "completed_without_json",
                    "returncode":slither_result.get("returncode"),
                    "output":str(slither_output),
                    "normalized_findings":len(slither_findings),
                    "note":"Non-zero exit codes may occur when detectors report findings; inspect the JSON and stderr."
                }
            except (OSError,TimeoutError,ValueError) as exc:
                slither_result={"status":"failed","error":str(exc)}
        else:
            slither_result={"status":"not_installed","note":"Install Slither to enable this analysis layer."}
    findings=heuristic+slither_findings
    return {
        "schema_version":1,
        "analysis_mode":"local_source_only",
        "source_root":str(source.resolve()),
        "coverage":{
            "solidity_files":len(inventory),
            "heuristic_leads":len(heuristic),
            "slither_findings":len(slither_findings),
            "tools":{"heuristics":"completed","slither":slither_result},
        },
        "findings":findings,
        "validation_policy":{
            "confirmed_vulnerabilities":0,
            "all_results_are_unverified":True,
            "requirements":["reproduce with a local test","confirm root cause and reachable preconditions","check deployed-source correspondence","check current program scope and exclusions","justify impact using program definitions","human review before external reporting"]
        }
    }
