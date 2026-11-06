"""Markdown report generator for human review."""
from pathlib import Path
from datetime import datetime,timezone
import json
def write_report(findings_path:Path,output:Path,program_name="Unspecified program"):
    data=json.loads(findings_path.read_text(encoding="utf-8")); findings=data.get("findings",[])
    lines=[f"# Security research notes — {program_name}","",f"Generated: {datetime.now(timezone.utc).isoformat()}","","> Draft for human review only. Automated heuristics are not confirmed vulnerabilities. Verify current program scope, exclusions, impact, and testing rules before submission.","",f"Potential leads: **{len(findings)}**",""]
    for item in findings:
        lines += [f"## {item.get('id','untracked')} — {item.get('title','Untitled')}","",f"- Category: {item.get('category','unknown')}",f"- Severity: {item.get('severity','undetermined')}",f"- Confidence: {item.get('confidence','unknown')}",f"- Status: {item.get('status','potential')}",f"- Source: {item.get('source','')}:{item.get('line','?')}",f"- Evidence: {item.get('evidence','')}","- Validation: required; no impact or exploitability is asserted.",""]
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text("\n".join(lines),encoding="utf-8"); return output
