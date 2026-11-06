"""Conservative source-review heuristics. Results are leads, not confirmed bugs."""
from pathlib import Path
import re
RULES=[
("SOL001","external-call-review","External call followed by state update; review ordering and reentrancy assumptions",r"\.call\s*(?:\{[^}]*\})?\s*\([^;]*\)[\s\S]{0,500}?\b\w+\s*(?:\+=|-=|=)"),
("SOL002","authorization-review","External/public function; review authorization requirements",r"function\s+\w+[^;{]*\b(?:external|public)\b[^;{]*\{"),
("SOL003","arithmetic-review","Unchecked arithmetic block; review compiler and overflow assumptions",r"unchecked\s*\{"),
("SOL004","delegatecall-review","delegatecall use; review target trust and storage context",r"\.delegatecall\s*\("),
("SOL005","tx-origin-review","tx.origin use; review authentication assumptions",r"\btx\.origin\b"),
("SOL006","timestamp-review","block.timestamp use; review time-dependence",r"\bblock\.timestamp\b"),
("SOL007","selfdestruct-review","selfdestruct use; review lifecycle semantics",r"\bselfdestruct\s*\("),
("SOL008","signature-review","ecrecover use; review domain, nonce, and malleability handling",r"\becrecover\s*\("),
("SOL009","low-level-call-review","Low-level call; review return value and callee assumptions",r"\.call\s*(?:\{[^}]*\})?\s*\(")]
def scan_sources(root: Path) -> list[dict[str, object]]:
    if not root.is_dir(): raise NotADirectoryError(f"Source directory does not exist: {root}")
    findings=[]
    for path in sorted(root.rglob("*.sol")):
        if any(p in {".git",".venv","node_modules","out","cache","lib","vendor"} for p in path.parts): continue
        try: lines=path.read_text(encoding="utf-8",errors="replace").splitlines()
        except OSError: continue
        for number,line in enumerate(lines,1):
            for rid,category,title,pattern in RULES:
                if re.search(pattern,line):
                    findings.append({"id":f"{rid}-{len(findings)+1:04d}","rule_id":rid,"category":category,"title":title,"severity":"undetermined","confidence":"low","status":"potential","source":str(path.resolve()),"line":number,"evidence":line.strip()[:500],"requires_manual_validation":True})
    return findings
