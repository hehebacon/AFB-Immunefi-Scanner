"""Public Immunefi program URL intake and evidence-based scope draft."""
from __future__ import annotations
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse, urljoin
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re

MAX_BYTES = 3_000_000
ALLOWED_HOSTS = {"immunefi.com", "www.immunefi.com"}

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]; self.links=[]; self.title_parts=[]
        self.in_title=False; self.skip_depth=0
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in {"script","style","noscript","svg"}: self.skip_depth += 1
        if tag=="title": self.in_title=True
        if tag=="a" and attrs.get("href"): self.links.append(attrs["href"])
        if tag=="meta":
            key=(attrs.get("property") or attrs.get("name") or "").lower()
            if key in {"og:title","description","og:description"} and attrs.get("content"):
                self.parts.append(attrs["content"])
    def handle_endtag(self, tag):
        if tag in {"script","style","noscript","svg"} and self.skip_depth: self.skip_depth-=1
        if tag=="title": self.in_title=False
    def handle_data(self, data):
        text=" ".join(data.split())
        if text and not self.skip_depth:
            self.parts.append(text)
            if self.in_title: self.title_parts.append(text)

def validate_program_url(url: str) -> tuple[str,str]:
    parsed=urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Only HTTPS Immunefi program URLs are accepted.")
    match=re.match(r"^/bug-bounty/([a-zA-Z0-9_-]+)/(?:information|scope|resources)/?$",parsed.path)
    if not match:
        raise ValueError("Expected an Immunefi URL: /bug-bounty/<program>/(information|scope|resources)/")
    return match.group(1), url

def fetch_program_page(url: str) -> dict:
    slug, clean_url=validate_program_url(url)
    request=Request(clean_url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.2 (public program information intake)","Accept":"text/html"})
    try:
        with urlopen(request,timeout=20) as response:
            final_url=response.geturl()
            if urlparse(final_url).hostname not in ALLOWED_HOSTS:
                raise ValueError("Redirect left the Immunefi domain; refusing to use the response.")
            raw=response.read(MAX_BYTES+1)
            status=response.status
            content_type=response.headers.get("Content-Type","")
    except (HTTPError,URLError,TimeoutError) as exc:
        raise RuntimeError(f"Could not fetch Immunefi program page: {exc}") from exc
    if len(raw)>MAX_BYTES: raise ValueError("Program page exceeded the 3 MB safety limit.")
    encoding="utf-8"
    match=re.search(r"charset=([\w-]+)",content_type,re.I)
    if match: encoding=match.group(1)
    html=raw.decode(encoding,errors="replace")
    parser=PageParser(); parser.feed(html)
    text="\n".join(parser.parts)
    text=re.sub(r"[ \t]+"," ",text)
    text=re.sub(r"\n{3,}","\n\n",text).strip()
    links=[]
    for href in parser.links:
        absolute=urljoin(final_url,href)
        parsed=urlparse(absolute)
        if parsed.scheme=="https" and parsed.hostname and absolute not in links:
            links.append(absolute)
    return {"slug":slug,"requested_url":clean_url,"final_url":final_url,"http_status":status,"content_type":content_type,"fetched_at":datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"title":" ".join(parser.title_parts).strip() or None,"text":text,"links":links,"html":html}

def _section_extract(text: str, terms: tuple[str,...]) -> list[str]:
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines()]
    lines=[x for x in lines if x]
    hits=[]
    for i,line in enumerate(lines):
        low=line.lower()
        if any(term in low for term in terms):
            excerpt=" ".join(lines[i:min(i+8,len(lines))])
            hits.append(excerpt[:1800])
    return list(dict.fromkeys(hits))[:15]

def build_scope_draft(page: dict) -> dict:
    text=page.get("combined_text",page["text"])
    scope_pages=[item for item in page.get("pages",[page]) if urlparse(item["final_url"]).path.rstrip("/").endswith("/scope")]
    scope_source="\n\n".join(item["text"] for item in scope_pages)
    scope_chunks=_section_extract(scope_source,("assets in scope",))
    scope_text=" ".join(scope_chunks)
    full_addresses=set(re.findall(r"\b0x[a-fA-F0-9]{40}\b",scope_text))
    partial_addresses=set(re.findall(r"\b0x[a-fA-F0-9]{4,12}\.\.\.[a-fA-F0-9]{4,12}\b",scope_text))
    scope_pages=[item for item in page.get("pages",[page]) if urlparse(item["final_url"]).path.rstrip("/").endswith("/scope")]
    scope_links=[link for item in scope_pages for link in item.get("links",[]) if urlparse(link).hostname and any(host in urlparse(link).hostname for host in ("etherscan.io","arbiscan.io","basescan.org"))]
    for link in scope_links:
        match=re.search(r"/address/(0x[a-fA-F0-9]{40})",link)
        if match: full_addresses.add(match.group(1))
    address_candidates=[{"address":a,"status":"candidate_only","evidence_source":"Immunefi Scope page or linked block explorer"} for a in sorted(full_addresses)]
    address_candidates.extend({"address_fragment":a,"status":"partial_unverified","evidence_source":"Immunefi Scope page"} for a in sorted(partial_addresses))
    chain_terms=("ethereum","arbitrum","optimism","polygon","base","bnb chain","avalanche","solana","fantom","gnosis")
    chains=sorted({term for term in chain_terms if term in text.lower()})
    return {
        "schema_version":1,
        "program_name":page["slug"],
        "program_url":page["requested_url"],
        "source_fetched_at":page["fetched_at"],
        "source_sha256":page["sha256"],
        "verification_status":"unverified_human_review_required",
        "in_scope_assets_candidates":address_candidates,
        "chain_mentions_candidates":chains,
        "scope_evidence":scope_chunks,
        "excluded_asset_evidence":_section_extract(text,("out of scope","out-of-scope","excluded assets")),
        "impact_evidence":_section_extract(text,("impacts in scope","impact in scope")),
        "testing_rule_evidence":_section_extract(text,("proof of concept","testing rules","testing restrictions","safe harbor","responsible disclosure")),
        "exclusion_evidence":_section_extract(text,("known issues","not accepted","exclusions","out of scope","excluded vulnerability")),
        "related_links":page["links"],
        "pages_reviewed":[{"url":p["final_url"],"sha256":p["sha256"]} for p in page.get("pages",[page])],
        "limitations":["Page text extraction may omit content rendered only by JavaScript.","Addresses found on the Scope page are candidates and require exact asset verification.","A page mention does not by itself prove that an asset or impact is eligible.","Third-party links are recorded as references but are not automatically fetched.","No contract probing, RPC calls, transactions, or live testing are performed."]
    }

def save_program_intake(url: str, workspace: Path) -> dict:
    from .workspace import initialize_workspace
    if not (workspace/"program"/"policy.yaml").exists():
        initialize_workspace(workspace)
    page=fetch_program_page(url)
    related=[]
    slug=page["slug"]
    # Derive sibling tabs from the validated program slug as a fallback for JS-rendered navigation.
    requested_tab=urlparse(url).path.rstrip("/").split("/")[-1]
    for tab in ("scope","resources"):
        if tab==requested_tab: continue
        tab_url=f"https://immunefi.com/bug-bounty/{slug}/{tab}/"
        try:
            fetched=fetch_program_page(tab_url)
            if fetched["http_status"]==200: related.append(fetched)
        except (RuntimeError,ValueError):
            pass
    for link in page["links"]:
        parsed=urlparse(link)
        if parsed.hostname not in ALLOWED_HOSTS: continue
        match=re.fullmatch(rf"/bug-bounty/{re.escape(slug)}/(scope|resources)/?",parsed.path)
        if match:
            if any(item["final_url"]==link for item in related): continue
            try: related.append(fetch_program_page(link))
            except (RuntimeError,ValueError): pass
    page["pages"]=[page]+related
    page["combined_text"]="\n\n".join(p["text"] for p in page["pages"])
    draft=build_scope_draft(page)
    program_dir=workspace/"program"
    program_dir.mkdir(parents=True,exist_ok=True)
    for item in page["pages"]:
        suffix=urlparse(item["final_url"]).path.rstrip("/").split("/")[-1]
        (program_dir/f"source-page-{suffix}.html").write_text(item["html"],encoding="utf-8")
        (program_dir/f"source-page-{suffix}.txt").write_text(item["text"],encoding="utf-8")
    intake={"slug":page["slug"],"requested_url":page["requested_url"],"pages":[{"url":p["final_url"],"http_status":p["http_status"],"title":p["title"],"fetched_at":p["fetched_at"],"sha256":p["sha256"]} for p in page["pages"]],"related_links":page["links"]}
    (program_dir/"intake.json").write_text(json.dumps(intake,indent=2),encoding="utf-8")
    (program_dir/"scope-draft.json").write_text(json.dumps(draft,indent=2),encoding="utf-8")

    resources_page=next((p for p in related if urlparse(p["final_url"]).path.rstrip("/").endswith("/resources")),None)
    if resources_page:
        from .source_discovery import download_linked_solidity_repo
        source_result=download_linked_solidity_repo(resources_page["links"],workspace/"reconnaissance"/"sources")
    else:
        source_result={"status":"resources_page_not_fetched"}
    (program_dir/"source-discovery.json").write_text(json.dumps(source_result,indent=2),encoding="utf-8")
    from .reference_intelligence import classify_references, fetch_github_history, fetch_audit_pdfs, crawl_documentation
    resource_links=resources_page["links"] if resources_page else []
    references=classify_references(resource_links)
    (program_dir/"references.json").write_text(json.dumps(references,indent=2),encoding="utf-8")
    history_result={"status":"no_repository_discovered"}
    if source_result.get("repository"):
        owner_repo=source_result["repository"]
        history_result=fetch_github_history("https://github.com/"+owner_repo,workspace/"reconnaissance"/"history")
    (program_dir/"github-history-status.json").write_text(json.dumps(history_result,indent=2),encoding="utf-8")
    pdf_result=fetch_audit_pdfs(references,workspace/"reconnaissance"/"references"/"audits")
    (program_dir/"audit-pdf-index.json").write_text(json.dumps(pdf_result,indent=2),encoding="utf-8")
    docs_result=crawl_documentation(references,workspace/"reconnaissance"/"docs")
    (program_dir/"documentation-crawl-index.json").write_text(json.dumps(docs_result,indent=2),encoding="utf-8")
    analysis_result={"status":"not_run"}
    if source_result.get("status")=="downloaded":
        from .inventory import inventory_sources
        from .detectors import scan_sources
        source_root=Path(source_result["local_path"])
        inventory=inventory_sources(source_root)
        leads=scan_sources(source_root)
        recon_dir=workspace/"reconnaissance"
        review_dir=workspace/"analysis"/"review-notes"
        recon_dir.mkdir(parents=True,exist_ok=True)
        review_dir.mkdir(parents=True,exist_ok=True)
        (recon_dir/"contracts.json").write_text(json.dumps({"repository":source_result["repository"],"files":inventory},indent=2),encoding="utf-8")
        (review_dir/"source-leads.json").write_text(json.dumps({"repository":source_result["repository"],"scope_status":"unverified","findings":leads},indent=2),encoding="utf-8")
        analysis_result={"status":"completed_local_heuristics","solidity_files":len(inventory),"potential_review_leads":len(leads),"scope_status":"unverified"}
    (program_dir/"local-analysis.json").write_text(json.dumps(analysis_result,indent=2),encoding="utf-8")

    lines=[f"# Program scope research — {page['slug']}","","- Official page: "+page["final_url"],"- Fetched: "+page["fetched_at"],"- Pages fetched: "+str(len(page["pages"])),"- Source SHA-256: "+page["sha256"],"","> Draft only. This is extracted public-page evidence, not a verified scope decision. Confirm current program rules before testing."]
    def add_section(title,key):
        lines.extend(["",f"## {title}"])
        values=draft[key]
        if not values: lines.append("- No matching evidence extracted; status: unknown.")
        else:
            for value in values: lines.append("- "+(json.dumps(value,ensure_ascii=False) if isinstance(value,dict) else str(value)))
    add_section("Potential in-scope asset addresses (unverified)","in_scope_assets_candidates")
    add_section("Chain mentions (unverified)","chain_mentions_candidates")
    add_section("Assets in Scope evidence","scope_evidence")
    add_section("Out-of-scope evidence","excluded_asset_evidence")
    add_section("Impacts in Scope evidence","impact_evidence")
    add_section("Testing rules and safe harbor","testing_rule_evidence")
    add_section("Exclusions and known issues","exclusion_evidence")
    lines.extend(["","## Source discovery",json.dumps(source_result,indent=2),"","## Public reference collection",json.dumps({"reference_count":len(references),"github_history":history_result,"audit_pdfs":pdf_result,"documentation":docs_result},indent=2),"","## Local source review",json.dumps(analysis_result,indent=2)])
    lines.extend(["","## Related links discovered on the official program pages"])
    lines.extend(["- "+link for link in page["links"]] or ["- None extracted."])
    lines.extend(["","## Limitations"]+["- "+x for x in draft["limitations"]])
    (program_dir/"scope-report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    outputs=[str(program_dir/("source-page-"+urlparse(item["final_url"]).path.rstrip("/").split("/")[-1]+"."+ext)) for item in page["pages"] for ext in ("html","txt")]
    outputs += [str(program_dir/x) for x in ("intake.json","scope-draft.json","source-discovery.json","references.json","github-history-status.json","audit-pdf-index.json","documentation-crawl-index.json","local-analysis.json","scope-report.md")]
    return {"slug":page["slug"],"http_status":page["http_status"],"title":page["title"],"source_sha256":page["sha256"],"asset_candidates":len(draft["in_scope_assets_candidates"]),"related_links":len(page["links"]),"program_pages_fetched":len(page["pages"]),"source_discovery":source_result,"reference_count":len(references),"github_history":history_result,"audit_pdfs":pdf_result,"local_analysis":analysis_result,"outputs":outputs}
