"""Read-only deployed-contract verification through Sourcify's public API."""
from __future__ import annotations
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from pathlib import Path
from datetime import datetime, timezone
import json, re

SOURCIFY_BASE="https://sourcify.dev/server/v2/contract"

def verify_targets(targets: list[dict], timeout: int=20) -> dict:
    results=[]
    for target in targets:
        chain_id=str(target.get("chain_id","")).strip()
        address=str(target.get("address","")).strip()
        label=str(target.get("label","")).strip()
        if not chain_id.isdigit() or not re.fullmatch(r"0x[a-fA-F0-9]{40}",address):
            results.append({"label":label,"chain_id":chain_id,"address":address,"status":"invalid_target"}); continue
        url=f"{SOURCIFY_BASE}/{quote(chain_id,safe='')}/{quote(address,safe='')}"
        request=Request(url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.3","Accept":"application/json"})
        try:
            with urlopen(request,timeout=timeout) as response:
                if response.status!=200:
                    results.append({"label":label,"chain_id":chain_id,"address":address,"status":"not_verified_or_unavailable","http_status":response.status}); continue
                raw=response.read(2_000_001)
            if len(raw)>2_000_000: raise ValueError("Sourcify response exceeded 2 MB")
            payload=json.loads(raw.decode("utf-8"))
            results.append({
                "label":label,"chain_id":chain_id,"address":address,
                "status":"verified_match" if payload.get("match") in {"exact_match","match"} else "verified_partial_or_unmatched",
                "match":payload.get("match"),
                "creation_match":payload.get("creationMatch"),
                "runtime_match":payload.get("runtimeMatch"),
                "compiler":payload.get("compiler"),
                "language":payload.get("language"),
                "verification_url":url,
                "evidence":payload
            })
        except HTTPError as exc:
            results.append({"label":label,"chain_id":chain_id,"address":address,"status":"not_verified_or_unavailable","http_status":exc.code})
        except (URLError,TimeoutError,ValueError,json.JSONDecodeError) as exc:
            results.append({"label":label,"chain_id":chain_id,"address":address,"status":"verification_error","error":str(exc)[:300]})
    return {
        "schema_version":1,
        "checked_at":datetime.now(timezone.utc).isoformat(),
        "provider":"Sourcify public verification API",
        "mode":"read_only_metadata_verification",
        "results":results,
        "policy":{"does_not_call_contract_methods":True,"does_not_send_transactions":True,"verified_match_is_not_scope_confirmation":True,"manual_review_required":True}
    }

def verify_targets_file(input_path: Path, output_path: Path) -> dict:
    payload=json.loads(input_path.read_text(encoding="utf-8"))
    targets=payload.get("targets",[]) if isinstance(payload,dict) else payload
    if not isinstance(targets,list): raise ValueError("Targets file must contain a list or {'targets': [...]} object.")
    result=verify_targets(targets)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
