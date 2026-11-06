"""Read-only Sourcify verification and local source-tree comparison."""
from __future__ import annotations
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re

SOURCIFY_BASE="https://sourcify.dev/server/v2/contract"

def _normalised_source_hash(value: str) -> str:
    return hashlib.sha256(value.replace("\r\n","\n").replace("\r","\n").encode("utf-8")).hexdigest()

def _compare_sources(remote_sources: dict, source_root: Path | None) -> dict:
    if source_root is None:
        return {"status":"not_requested","files_compared":0,"exact_matches":0,"mismatches":[],"missing":[]}
    if not source_root.is_dir():
        return {"status":"source_directory_missing","files_compared":0,"exact_matches":0,"mismatches":[],"missing":[]}
    exact=[]; mismatches=[]; missing=[]
    for remote_path, remote_record in (remote_sources or {}).items():
        remote_content=remote_record.get("content") if isinstance(remote_record,dict) else None
        if not isinstance(remote_content,str):
            missing.append({"path":remote_path,"reason":"Sourcify response did not include source content"}); continue
        candidate=source_root/Path(remote_path)
        if not candidate.is_file():
            # Match full relative suffix only; do not silently equate same basenames from different folders.
            matches=[p for p in source_root.rglob(Path(remote_path).name) if p.is_file() and tuple(p.parts[-len(Path(remote_path).parts):])==tuple(Path(remote_path).parts)]
            if len(matches)==1: candidate=matches[0]
            else:
                missing.append({"path":remote_path,"reason":"not found in downloaded source tree" if not matches else "ambiguous relative path"}); continue
        try: local_content=candidate.read_text(encoding="utf-8")
        except (OSError,UnicodeError) as exc:
            missing.append({"path":remote_path,"reason":str(exc)[:200]}); continue
        local_hash=_normalised_source_hash(local_content); remote_hash=_normalised_source_hash(remote_content)
        record={"path":remote_path,"local_path":str(candidate),"local_sha256":local_hash,"sourcify_sha256":remote_hash}
        if local_hash==remote_hash: exact.append(record)
        else: mismatches.append(record)
    count=len(exact)+len(mismatches)
    status="exact_source_tree_match" if count and not mismatches and not missing else ("source_tree_mismatch" if mismatches else ("incomplete_source_tree" if missing else "no_sources_returned"))
    return {"status":status,"files_compared":count,"exact_matches":len(exact),"mismatches":mismatches,"missing":missing,"exact_match_is_textual_file_identity":True}

def verify_targets(targets: list[dict], timeout: int=20, source_root: Path | None=None) -> dict:
    results=[]
    if len(targets)>25:
        raise ValueError("At most 25 explicit deployment targets may be checked per run.")
    for target in targets:
        chain_id=str(target.get("chain_id","")).strip()
        address=str(target.get("address","")).strip()
        label=str(target.get("label","")).strip()
        if not chain_id.isdigit() or not re.fullmatch(r"0x[a-fA-F0-9]{40}",address):
            results.append({"label":label,"chain_id":chain_id,"address":address,"status":"invalid_target"}); continue
        url=f"{SOURCIFY_BASE}/{quote(chain_id,safe='')}/{quote(address,safe='')}?fields=sources,compilation,proxyResolution"
        request=Request(url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.3","Accept":"application/json"})
        try:
            with urlopen(request,timeout=timeout) as response:
                raw=response.read(8_000_001)
            if len(raw)>8_000_000: raise ValueError("Sourcify response exceeded 8 MB")
            payload=json.loads(raw.decode("utf-8"))
            match=payload.get("match")
            result={
                "label":label,"chain_id":chain_id,"address":address,
                "status":"verified_match" if match=="exact_match" else ("verified_partial_match" if match=="match" else "not_verified_or_unavailable"),
                "match":match,"creation_match":payload.get("creationMatch"),"runtime_match":payload.get("runtimeMatch"),
                "compiler":(payload.get("compilation") or {}).get("compilerVersion"),
                "language":(payload.get("compilation") or {}).get("language"),
                "verified_at":payload.get("verifiedAt"),"verification_url":url,
                "github_source_comparison":_compare_sources(payload.get("sources") or {},source_root),
                "proxy_resolution":payload.get("proxyResolution")
            }
            result["combined_status"]="exact_deployment_and_source_tree_match" if result["status"]=="verified_match" and result["github_source_comparison"]["status"]=="exact_source_tree_match" else "manual_review_required"
            results.append(result)
        except HTTPError as exc:
            results.append({"label":label,"chain_id":chain_id,"address":address,"status":"not_verified_or_unavailable","http_status":exc.code})
        except (URLError,TimeoutError,ValueError,json.JSONDecodeError) as exc:
            results.append({"label":label,"chain_id":chain_id,"address":address,"status":"verification_error","error":str(exc)[:300]})
    return {
        "schema_version":1,"checked_at":datetime.now(timezone.utc).isoformat(),
        "provider":"Sourcify API v2","mode":"read_only_deployed_bytecode_and_source_comparison",
        "results":results,
        "policy":{"does_not_call_contract_methods":True,"does_not_send_transactions":True,"verified_match_is_not_scope_confirmation":True,"local_source_comparison_is_exact_text_after_newline_normalisation":True,"proxy_implementations_may_require_separate_targets":True,"manual_review_required":True}
    }

def verify_targets_file(input_path: Path, output_path: Path, source_root: Path | None=None) -> dict:
    payload=json.loads(input_path.read_text(encoding="utf-8"))
    targets=payload.get("targets",[]) if isinstance(payload,dict) else payload
    if not isinstance(targets,list): raise ValueError("Targets file must contain a list or {'targets': [...]} object.")
    result=verify_targets(targets,source_root=source_root)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
