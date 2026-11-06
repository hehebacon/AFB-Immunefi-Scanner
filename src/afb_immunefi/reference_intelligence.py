"""Passive collection of public references, linked audit PDFs and GitHub commit metadata."""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
import ipaddress, json, re

MAX_PDF_BYTES=20_000_000
MAX_PDFS=12
MAX_COMMITS=100

def _public_https_url(url: str) -> bool:
    parsed=urlparse(url)
    if parsed.scheme!="https" or not parsed.hostname:
        return False
    try:
        ip=ipaddress.ip_address(parsed.hostname)
        if not ip.is_global: return False
    except ValueError:
        if parsed.hostname in {"localhost"} or parsed.hostname.endswith((".local",".internal")):
            return False
    return True

def classify_references(links: list[str]) -> list[dict]:
    results=[]
    for url in dict.fromkeys(links):
        parsed=urlparse(url)
        if not _public_https_url(url): continue
        host=parsed.hostname or ""
        path=parsed.path.lower()
        if host in {"github.com","www.github.com"}:
            parts=[p for p in parsed.path.split("/") if p]
            kind="github_repository" if len(parts)>=2 else "github_reference"
        elif path.endswith(".pdf") or ".pdf?" in url.lower():
            kind="audit_or_document_pdf"
        elif any(token in host for token in ("docs.","readthedocs.","gitbook.")):
            kind="documentation"
        elif any(token in host for token in ("etherscan.io","arbiscan.io","basescan.org")):
            kind="block_explorer"
        else:
            kind="external_reference"
        results.append({"url":url,"host":host,"kind":kind})
    return results

def fetch_github_history(repo_url: str, output_dir: Path) -> dict:
    parsed=urlparse(repo_url)
    if parsed.hostname not in {"github.com","www.github.com"}:
        return {"status":"unsupported_repository_host"}
    parts=[p for p in parsed.path.split("/") if p]
    if len(parts)<2:
        return {"status":"invalid_repository_url"}
    owner,repo=parts[0],parts[1].removesuffix(".git")
    if owner in {"features","topics","collections","marketplace","orgs","login"}:
        return {"status":"not_a_repository_url"}
    api=f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={MAX_COMMITS}"
    request=Request(api,headers={"User-Agent":"AFB-Immunefi-Scanner/0.2","Accept":"application/vnd.github+json"})
    try:
        with urlopen(request,timeout=25) as response:
            if urlparse(response.geturl()).hostname!="api.github.com":
                return {"status":"redirect_rejected"}
            payload=json.loads(response.read(8_000_000).decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        return {"status":"fetch_failed","repository":f"{owner}/{repo}","error":str(exc)}
    if not isinstance(payload,list):
        return {"status":"unexpected_api_response","repository":f"{owner}/{repo}"}
    commits=[]
    for item in payload[:MAX_COMMITS]:
        commit=item.get("commit",{})
        author=commit.get("author") or {}
        commits.append({
            "sha":item.get("sha"),
            "url":item.get("html_url"),
            "date":author.get("date"),
            "author":author.get("name"),
            "message":(commit.get("message") or "").splitlines()[0][:300]
        })
    output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/f"{owner}-{repo}-commits.json"
    target.write_text(json.dumps({"repository":f"{owner}/{repo}","fetched_at":datetime.now(timezone.utc).isoformat(),"commits":commits},indent=2),encoding="utf-8")
    return {"status":"completed","repository":f"{owner}/{repo}","commit_count":len(commits),"output":str(target)}

def fetch_audit_pdfs(references: list[dict], output_dir: Path) -> dict:
    candidates=[item["url"] for item in references if item.get("kind")=="audit_or_document_pdf"][:MAX_PDFS]
    output_dir.mkdir(parents=True,exist_ok=True)
    saved=[]; failures=[]
    for index,url in enumerate(candidates,1):
        parsed=urlparse(url)
        if not _public_https_url(url): continue
        request=Request(url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.2","Accept":"application/pdf"})
        try:
            with urlopen(request,timeout=30) as response:
                final=urlparse(response.geturl())
                if final.scheme!="https" or final.hostname!=parsed.hostname:
                    failures.append({"url":url,"reason":"cross-host redirect rejected"}); continue
                raw=response.read(MAX_PDF_BYTES+1)
            if len(raw)>MAX_PDF_BYTES:
                failures.append({"url":url,"reason":"file exceeds 20 MB"}); continue
            if not raw.startswith(b"%PDF-"):
                failures.append({"url":url,"reason":"response is not a PDF"}); continue
            name=re.sub(r"[^A-Za-z0-9._-]+","_",Path(parsed.path).name or f"audit-{index}.pdf")
            if not name.lower().endswith(".pdf"): name+= ".pdf"
            target=output_dir/f"{index:02d}-{name}"
            target.write_bytes(raw)
            record={"url":url,"path":str(target),"bytes":len(raw)}
            try:
                from pypdf import PdfReader
                reader=PdfReader(str(target),strict=False)
                pages=[]
                for page_number,page in enumerate(reader.pages[:120],1):
                    try:
                        extracted=(page.extract_text() or "").strip()
                    except Exception:
                        extracted=""
                    if extracted: pages.append({"page":page_number,"text":extracted[:12000]})
                text_path=target.with_suffix(".txt")
                text_path.write_text("\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages),encoding="utf-8")
                record.update({"pages_read":len(reader.pages),"pages_with_text":len(pages),"text_path":str(text_path)})
            except ImportError:
                record["text_extraction"]="pypdf not installed"
            except Exception as exc:
                record["text_extraction_error"]=str(exc)[:300]
            saved.append(record)
        except (HTTPError,URLError,TimeoutError) as exc:
            failures.append({"url":url,"reason":str(exc)[:300]})
    return {"status":"completed","candidates":len(candidates),"saved":saved,"failures":failures}
