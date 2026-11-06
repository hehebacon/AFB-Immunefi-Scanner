"""Bounded passive collection of public program references, Git history, docs and audits."""
from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html.parser import HTMLParser
from datetime import datetime, timezone
import ipaddress, json, re, subprocess, shutil

MAX_PDF_BYTES=20_000_000
MAX_PDFS=20
MAX_COMMITS=1000
MAX_DOC_PAGES=40
MAX_DOC_DEPTH=2
MAX_DOC_BYTES=2_000_000
MAX_OCR_PAGES=120

def _public_https_url(url: str) -> bool:
    parsed=urlparse(url)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    try:
        ip=ipaddress.ip_address(parsed.hostname)
        return ip.is_global
    except ValueError:
        return parsed.hostname not in {"localhost"} and not parsed.hostname.endswith((".local",".internal"))

def _read_limited(response, limit: int) -> bytes:
    data=response.read(limit+1)
    if len(data)>limit: raise ValueError(f"response exceeds {limit} bytes")
    return data

def classify_references(links: list[str]) -> list[dict]:
    results=[]
    for url in dict.fromkeys(links):
        if not _public_https_url(url): continue
        parsed=urlparse(url); host=parsed.hostname or ""; path=parsed.path.lower()
        if host in {"github.com","www.github.com"}:
            parts=[p for p in parsed.path.split("/") if p]
            kind="github_repository" if len(parts)>=2 else "github_reference"
        elif path.endswith(".pdf"): kind="audit_or_document_pdf"
        elif any(token in host for token in ("docs.","readthedocs.","gitbook.")): kind="documentation"
        elif any(host==domain or host.endswith("."+domain) for domain in ("etherscan.io","arbiscan.io","basescan.org","optimistic.etherscan.io","polygonscan.com","bscscan.com")): kind="block_explorer"
        else: kind="external_reference"
        results.append({"url":url,"host":host,"kind":kind})
    return results

def fetch_github_history(repo_url: str, output_dir: Path, max_commits: int=MAX_COMMITS) -> dict:
    parsed=urlparse(repo_url)
    if parsed.hostname not in {"github.com","www.github.com"}: return {"status":"unsupported_repository_host"}
    parts=[p for p in parsed.path.split("/") if p]
    if len(parts)<2: return {"status":"invalid_repository_url"}
    owner,repo=parts[0],parts[1].removesuffix(".git")
    if owner in {"features","topics","collections","marketplace","orgs","login"}: return {"status":"not_a_repository_url"}
    limit=max(1,min(int(max_commits),5000)); commits=[]; pages=0; truncated=False
    try:
        while len(commits)<limit:
            page=pages+1
            api=f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=100&page={page}"
            req=Request(api,headers={"User-Agent":"AFB-Immunefi-Scanner/0.3","Accept":"application/vnd.github+json"})
            with urlopen(req,timeout=25) as response:
                if urlparse(response.geturl()).hostname!="api.github.com": return {"status":"redirect_rejected"}
                payload=json.loads(_read_limited(response,8_000_000).decode("utf-8"))
            if not isinstance(payload,list): return {"status":"unexpected_api_response","repository":f"{owner}/{repo}"}
            pages+=1
            for item in payload:
                commit=item.get("commit",{}); author=commit.get("author") or {}
                commits.append({"sha":item.get("sha"),"url":item.get("html_url"),"date":author.get("date"),"author":author.get("name"),"message":(commit.get("message") or "").splitlines()[0][:300]})
                if len(commits)>=limit: break
            if len(payload)<100:
                break
        else: truncated=True
    except (HTTPError,URLError,TimeoutError,ValueError,json.JSONDecodeError) as exc:
        return {"status":"fetch_failed","repository":f"{owner}/{repo}","commits_collected":len(commits),"pages_collected":pages,"error":str(exc)[:300]}
    output_dir.mkdir(parents=True,exist_ok=True)
    target=output_dir/f"{owner}-{repo}-commits.json"
    target.write_text(json.dumps({"repository":f"{owner}/{repo}","fetched_at":datetime.now(timezone.utc).isoformat(),"requested_limit":limit,"pages_collected":pages,"truncated_at_limit":truncated,"commits":commits},indent=2),encoding="utf-8")
    return {"status":"completed","repository":f"{owner}/{repo}","commit_count":len(commits),"pages_collected":pages,"truncated_at_limit":truncated,"output":str(target)}

class _DocParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.links=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {"script","style","noscript","svg"}: self.skip+=1
        if tag=="a" and attrs.get("href"): self.links.append(attrs["href"])
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript","svg"} and self.skip: self.skip-=1
    def handle_data(self,data):
        value=" ".join(data.split())
        if value and not self.skip: self.parts.append(value)

def crawl_documentation(references: list[dict], output_dir: Path, max_pages: int=MAX_DOC_PAGES, max_depth: int=MAX_DOC_DEPTH) -> dict:
    """Crawl only explicitly linked documentation hosts; same-host links, bounded depth/bytes/pages."""
    seeds=[x["url"] for x in references if x.get("kind")=="documentation" and _public_https_url(x.get("url",""))]
    queue=[(u,0) for u in seeds]; seen=set(); saved=[]; failures=[]
    output_dir.mkdir(parents=True,exist_ok=True)
    while queue and len(saved)<max(1,min(max_pages,100)):
        url,depth=queue.pop(0)
        if url in seen: continue
        seen.add(url); parsed=urlparse(url)
        try:
            req=Request(url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.3","Accept":"text/html"})
            with urlopen(req,timeout=20) as response:
                final=urlparse(response.geturl())
                if final.scheme!="https" or final.hostname!=parsed.hostname:
                    failures.append({"url":url,"reason":"cross-host redirect rejected"}); continue
                ctype=response.headers.get("Content-Type","").lower()
                if "html" not in ctype:
                    failures.append({"url":url,"reason":"not HTML"}); continue
                raw=_read_limited(response,MAX_DOC_BYTES)
            html=raw.decode("utf-8",errors="replace"); parser=_DocParser(); parser.feed(html)
            text="\n".join(parser.parts)
            name=f"{len(saved)+1:03d}-{re.sub(r'[^A-Za-z0-9_-]+','_',parsed.hostname or 'docs')}.txt"
            target=output_dir/name; target.write_text(f"URL: {url}\nDEPTH: {depth}\n\n{text}",encoding="utf-8")
            saved.append({"url":url,"path":str(target),"depth":depth,"bytes":len(raw),"sha256":__import__("hashlib").sha256(raw).hexdigest(),"characters":len(text)})
            if depth<max_depth:
                for href in parser.links:
                    nxt=urljoin(url,href); p=urlparse(nxt)
                    if p.scheme=="https" and p.hostname==parsed.hostname and nxt not in seen and not p.fragment:
                        queue.append((nxt,depth+1))
        except (HTTPError,URLError,TimeoutError,ValueError) as exc:
            failures.append({"url":url,"reason":str(exc)[:250]})
    return {"status":"completed","seed_count":len(seeds),"pages_saved":len(saved),"queue_remaining":len(queue),"page_limit":max_pages,"depth_limit":max_depth,"saved":saved,"failures":failures}

def _ocr_pdf(pdf_path: Path, output_path: Path, page_numbers: list[int], max_pages: int=MAX_OCR_PAGES) -> dict:
    if not shutil.which("tesseract") or not shutil.which("pdftoppm"):
        return {"status":"unavailable","reason":"Install tesseract-ocr and poppler-utils to OCR scanned PDF pages."}
    try:
        from pypdf import PdfReader
        reader=PdfReader(str(pdf_path),strict=False)
        selected=page_numbers[:max_pages]; total=len(selected); ocr_text=[]; attempted=0
        import tempfile
        with tempfile.TemporaryDirectory(prefix="afb-ocr-") as tmp:
            for page_number in selected:
                image_prefix=str(Path(tmp)/f"page-{page_number}")
                proc=subprocess.run(["pdftoppm","-f",str(page_number),"-l",str(page_number),"-r","160","-png","-singlefile",str(pdf_path),image_prefix],capture_output=True,text=True,timeout=45,check=False)
                image_path=Path(image_prefix+".png")
                if proc.returncode or not image_path.exists(): continue
                attempted+=1
                out=subprocess.run(["tesseract",str(image_path),"stdout","-l","eng"],capture_output=True,text=True,timeout=45,check=False)
                if out.returncode==0 and out.stdout.strip(): ocr_text.append(f"[OCR Page {page_number}]\n{out.stdout.strip()[:12000]}")
        if ocr_text:
            with output_path.open("a",encoding="utf-8") as stream: stream.write("\n\n"+"\n\n".join(ocr_text)+"\n")
        return {"status":"completed","pages_considered":total,"pages_rendered":attempted,"pages_with_text":len(ocr_text),"page_cap":max_pages,"truncated":len(page_numbers)>max_pages}
    except (ImportError,OSError,ValueError,subprocess.TimeoutExpired) as exc:
        return {"status":"failed","error":str(exc)[:300]}

def fetch_audit_pdfs(references: list[dict], output_dir: Path, enable_ocr: bool=True) -> dict:
    candidates=[item["url"] for item in references if item.get("kind")=="audit_or_document_pdf"][:MAX_PDFS]
    output_dir.mkdir(parents=True,exist_ok=True); saved=[]; failures=[]
    for index,url in enumerate(candidates,1):
        parsed=urlparse(url)
        try:
            request=Request(url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.3","Accept":"application/pdf"})
            with urlopen(request,timeout=30) as response:
                final=urlparse(response.geturl())
                if final.scheme!="https" or final.hostname!=parsed.hostname:
                    failures.append({"url":url,"reason":"cross-host redirect rejected"}); continue
                raw=_read_limited(response,MAX_PDF_BYTES)
            if not raw.startswith(b"%PDF-"):
                failures.append({"url":url,"reason":"response is not a PDF"}); continue
            name=re.sub(r"[^A-Za-z0-9._-]+","_",Path(parsed.path).name or f"audit-{index}.pdf")
            if not name.lower().endswith(".pdf"): name+=".pdf"
            target=output_dir/f"{index:02d}-{name}"; target.write_bytes(raw)
            record={"url":url,"path":str(target),"bytes":len(raw)}
            try:
                from pypdf import PdfReader
                reader=PdfReader(str(target),strict=False); pages=[]; scanned=[]
                for page_number,page in enumerate(reader.pages[:MAX_OCR_PAGES],1):
                    try: extracted=(page.extract_text() or "").strip()
                    except Exception: extracted=""
                    if extracted: pages.append({"page":page_number,"text":extracted[:12000]})
                    else: scanned.append(page_number)
                text_path=target.with_suffix(".txt")
                text_path.write_text("\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages),encoding="utf-8")
                record.update({"pages_read":len(reader.pages),"pages_with_text":len(pages),"pages_without_text":scanned,"text_path":str(text_path)})
                record["ocr"]=_ocr_pdf(target,text_path,scanned) if enable_ocr and scanned else {"status":"not_needed" if not scanned else "disabled"}
            except ImportError: record["text_extraction"]="pypdf not installed"
            except Exception as exc: record["text_extraction_error"]=str(exc)[:300]
            saved.append(record)
        except (HTTPError,URLError,TimeoutError,ValueError) as exc:
            failures.append({"url":url,"reason":str(exc)[:300]})
    return {"status":"completed","candidates":len(candidates),"saved":saved,"failures":failures}
