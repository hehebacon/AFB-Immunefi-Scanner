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
    match=re.match(r"^/bug-bounty/([a-zA-Z0-9_-]+)/information/?$",parsed.path)
    if not match:
        raise ValueError("Expected URL format: https://immunefi.com/bug-bounty/<program>/information/")
    return match.group(1), url

def fetch_program_page(url: str) -> dict:
    slug, clean_url=validate_program_url(url)
    request=Request(clean_url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.2 (public program information intake)","Accept":"text/html"})
    try:
        with urlopen(request,timeout=20) as response:
            final_url=response.geturl()
            if urlparse(final_url).hostname not in ALLOWED_HOSTS:
                raise ValueError("Redirect left the Immunefi domain; refusing to follow it.")
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
        if parsed.scheme=="https" and parsed.hostname and (parsed.hostname in ALLOWED_HOSTS or parsed.hostname.endswith(".immunefi.com")):
            if absolute not in links: links.append(absolute)
    return {"slug":slug,"requested_url":clean_url,"final_url":final_url,"http_status":status,"content_type":content_type,"fetched_at":datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"title":" ".join(parser.title_parts).strip() or None,"text":text,"links":links,"html":html}

def _section_extract(text: str, terms: tuple[str,...]) -> list[str]:
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines()]
    lines=[x for x in lines if x]
    hits=[]
    for i,line in enumerate(lines):
        low=line.lower()
        if any(term in low for term in terms):
            excerpt=" ".join(lines[i:min(i+7,len(lines))])
            hits.append(excerpt[:1600])
    return list(dict.fromkeys(hits))[:12]

def build_scope_draft(page: dict) -> dict:
    text=page["text"]
    address_candidates=sorted(set(re.findall(r"\b0x[a-fA-F0-9]{40}\b",text)))
    chain_terms=("ethereum","arbitrum","optimism","polygon","base","bnb chain","avalanche","solana","fantom","gnosis")
    chains=sorted({term for term in chain_terms if term in text.lower()})
    return {
        "schema_version":1,
        "program_name":page["slug"],
        "program_url":page["requested_url"],
        "source_fetched_at":page["fetched_at"],
        "source_sha256":page["sha256"],
        "verification_status":"unverified_human_review_required",
        "in_scope_assets_candidates":[{"address":a,"status":"candidate_only","evidence_source":page["final_url"]} for a in address_candidates],
        "chain_mentions_candidates":chains,
        "scope_evidence":_section_extract(text,("in-scope","in scope","eligible assets","assets in scope","smart contracts")),
        "excluded_asset_evidence":_section_extract(text,("out of scope","out-of-scope","excluded assets")),
        "impact_evidence":_section_extract(text,("impacts in scope","impact in scope","impact","severity")),
        "testing_rule_evidence":_section_extract(text,("proof of concept","testing rules","testing restrictions","safe harbor","responsible disclosure")),
        "exclusion_evidence":_section_extract(text,("known issues","not accepted","exclusions","out of scope","excluded vulnerability")),
        "related_official_links":page["links"],
        "limitations":["Page text extraction may omit content rendered only by JavaScript.","Address and chain matches are candidates, not confirmed in-scope assets.","No third-party pages, APIs, RPC endpoints, or live targets were queried.","A human must compare every claim with the current official program rules."]
    }

def save_program_intake(url: str, workspace: Path) -> dict:
    page=fetch_program_page(url)
    draft=build_scope_draft(page)
    program_dir=workspace/"program"; program_dir.mkdir(parents=True,exist_ok=True)
    (program_dir/"source-page.html").write_text(page["html"],encoding="utf-8")
    (program_dir/"source-page.txt").write_text(page["text"],encoding="utf-8")
    (program_dir/"intake.json").write_text(json.dumps({k:v for k,v in page.items() if k not in {"html","text"}},indent=2),encoding="utf-8")
    (program_dir/"scope-draft.json").write_text(json.dumps(draft,indent=2),encoding="utf-8")
    lines=[f"# Program scope research — {page['slug']}","",f"- Official page: {page['final_url']}",f"- Fetched: {page['fetched_at']}",f"- HTTP status: {page['http_status']}",f"- Source SHA-256: {page['sha256']}","","> Draft only. This is extracted public-page evidence, not a verified scope decision. Confirm the live program rules before testing."]
    def add_section(title,key):
        lines.extend(["",f"## {title}"])
        values=draft[key]
        if not values: lines.append("- No matching evidence extracted; status: unknown.")
        else:
            for value in values: lines.append(f"- {value}")
    add_section("Potential asset addresses (unverified)","in_scope_assets_candidates")
    add_section("Chain mentions (unverified)","chain_mentions_candidates")
    add_section("In-scope evidence","scope_evidence")
    add_section("Out-of-scope evidence","excluded_asset_evidence")
    add_section("Impact evidence","impact_evidence")
    add_section("Testing rules and safe harbor","testing_rule_evidence")
    add_section("Exclusions and known issues","exclusion_evidence")
    lines.extend(["","## Related Immunefi links"])
    lines.extend([f"- {link}" for link in page["links"]] or ["- None extracted."])
    lines.extend(["","## Limitations"]+[f"- {x}" for x in draft["limitations"]])
    (program_dir/"scope-report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"slug":page["slug"],"http_status":page["http_status"],"title":page["title"],"source_sha256":page["sha256"],"asset_candidates":len(draft["in_scope_assets_candidates"]),"official_links":len(page["links"]),"outputs":[str(program_dir/x) for x in ("source-page.html","source-page.txt","intake.json","scope-draft.json","scope-report.md")]}
