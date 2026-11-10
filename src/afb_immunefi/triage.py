"""Normalize, deduplicate and benchmark local analyzer outputs."""
from __future__ import annotations
import json
import re
from pathlib import Path

def _key(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

def _location_key(item):
    source = str(item.get("source") or item.get("file") or "").replace("\\", "/")
    line = item.get("line")
    if line is None:
        lines = item.get("lines") or []
        line = lines[0] if lines else None
    return source, line

def load_slither_report(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    output = []
    for index, detector in enumerate(payload.get("results", {}).get("detectors", []), 1):
        for element in detector.get("elements") or [{}]:
            mapping = element.get("source_mapping") or {}
            output.append({
                "id": f"SLITHER-{index:04d}-{len(output)+1:02d}",
                "analyzer": "slither",
                "rule_id": detector.get("check", "unknown"),
                "title": detector.get("check", "Slither finding"),
                "description": (detector.get("description") or "")[:4000],
                "severity": (detector.get("impact") or "undetermined").lower(),
                "confidence": (detector.get("confidence") or "unknown").lower(),
                "source": mapping.get("filename_relative") or mapping.get("filename_absolute"),
                "line": (mapping.get("lines") or [None])[0],
                "status": "tool_reported_unverified",
            })
    return output

def load_aderyn_report(path: Path):
    """Conservative Markdown parser; retains heading context and nearby location hints."""
    text = path.read_text(encoding="utf-8", errors="replace")
    output = []
    matches = list(re.finditer(r"(?m)^#{2,4}\s+(.+)$", text))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.end():section_end]
        severity_match = re.search(r"(?i)\b(critical|high|medium|low|informational)\b", title + " " + section[:500])
        location_match = re.search(r"(?m)(?:File|Location|Source):\s*([^\n:]+)(?::(\d+))?", section)
        output.append({
            "id": f"ADERYN-{index+1:04d}",
            "analyzer": "aderyn",
            "rule_id": _key(title) or "aderyn-finding",
            "title": title[:300],
            "description": section[:2000].strip(),
            "severity": severity_match.group(1).lower() if severity_match else "undetermined",
            "confidence": "unknown",
            "source": location_match.group(1).strip() if location_match else None,
            "line": int(location_match.group(2)) if location_match and location_match.group(2) else None,
            "status": "tool_reported_unverified",
        })
    return output

def load_echidna_report(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    output = []
    tests = payload.get("tests", {}) if isinstance(payload, dict) else {}
    iterable = [(str(i), item) for i, item in enumerate(tests)] if isinstance(tests, list) else list(tests.items()) if isinstance(tests, dict) else []
    for name, result in iterable:
        if not isinstance(result, dict):
            continue
        status = str(result.get("status") or result.get("result") or "").lower()
        if status not in {"falsified", "failed", "failure", "counterexample"}:
            continue
        output.append({
            "id": f"ECHIDNA-{len(output)+1:04d}",
            "analyzer": "echidna",
            "rule_id": "echidna-property",
            "title": f"Property falsified: {name}",
            "description": json.dumps(result, sort_keys=True)[:3000],
            "severity": "undetermined",
            "confidence": "counterexample_generated",
            "source": result.get("contract"),
            "line": None,
            "status": "counterexample_requires_reproduction",
        })
    return output

def deduplicate_findings(findings):
    groups = {}
    for finding in findings:
        source, line = _location_key(finding)
        title = _key(finding.get("title") or finding.get("rule_id"))
        key = (source, int(line), title) if source and line is not None else ("unlocated", finding.get("analyzer"), finding.get("id"))
        if key not in groups:
            groups[key] = {**finding, "analyzers": [finding.get("analyzer", "unknown")], "duplicates": []}
        else:
            group = groups[key]
            analyzer = finding.get("analyzer", "unknown")
            if analyzer not in group["analyzers"]:
                group["analyzers"].append(analyzer)
            group["duplicates"].append({"id": finding.get("id"), "analyzer": analyzer, "rule_id": finding.get("rule_id")})
    return list(groups.values())

def benchmark_findings(detected, manifest: dict):
    positives = set(manifest.get("positive_cases", []))
    negatives = set(manifest.get("negative_cases", []))
    detected_keys = {str(item.get("benchmark_key") or item.get("rule_id") or item.get("id")) for item in detected}
    tp = len(positives & detected_keys)
    fp = len(negatives & detected_keys)
    fn = len(positives - detected_keys)
    tn = len(negatives - detected_keys)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "corpus": manifest.get("name", "user-supplied-labeled-corpus"),
        "corpus_size": len(positives | negatives),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall,
        "f1": (2 * precision * recall / (precision + recall)) if precision is not None and recall is not None and precision + recall else None,
        "warning": "Metrics are valid only for the explicitly labeled corpus; they do not estimate real-world scanner accuracy.",
    }

def build_triage_report(*, slither=None, aderyn=None, echidna=None, logic=None):
    all_findings = []
    for report in (slither, aderyn, echidna, logic):
        if isinstance(report, list):
            all_findings.extend(report)
        elif isinstance(report, dict):
            all_findings.extend(report.get("findings", []))
    deduped = deduplicate_findings(all_findings)
    return {
        "schema_version": 1,
        "raw_finding_count": len(all_findings),
        "deduplicated_finding_count": len(deduped),
        "findings": deduped,
        "validation_status": "unverified_until_local_test_reproduction",
    }
