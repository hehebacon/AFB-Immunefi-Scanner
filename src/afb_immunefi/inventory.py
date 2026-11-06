"""Local Solidity source inventory; no remote probing."""
from pathlib import Path
import hashlib, re
SKIP_DIRS={".git",".venv","node_modules","out","cache","lib","vendor","__pycache__"}
def inventory_sources(root: Path) -> list[dict[str, object]]:
    if not root.is_dir(): raise NotADirectoryError(f"Source directory does not exist: {root}")
    records=[]
    for path in sorted(root.rglob("*.sol")):
        if any(part in SKIP_DIRS for part in path.parts): continue
        try: raw=path.read_bytes(); source=raw.decode("utf-8",errors="replace")
        except OSError: continue
        pragma=re.search(r"pragma\s+solidity\s+([^;]+);",source)
        records.append({"path":str(path.resolve()),"relative_path":str(path.relative_to(root)),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"pragma":pragma.group(1) if pragma else "unknown","contracts":sorted(set(re.findall(r"\b(?:contract|interface|library)\s+(\w+)",source))),"imports":re.findall(r'import\s+(?:[^;]*?from\s+)?["\']([^"\']+)["\']\s*;',source)})
    return records
