"""Download Solidity sources from a GitHub repository linked by the program Resources page."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, BadZipFile
import json

def download_linked_solidity_repo(links: list[str], destination: Path) -> dict:
    candidates=[]
    for link in links:
        parsed=urlparse(link)
        parts=[part for part in parsed.path.split("/") if part]
        if parsed.scheme=="https" and parsed.hostname in {"github.com","www.github.com"} and len(parts)>=2:
            owner,repo=parts[0],parts[1].removesuffix(".git")
            if owner not in {"features","topics","collections","marketplace","orgs","login"}:
                candidates.append((owner,repo))
    if not candidates:
        return {"status":"no_github_repository_link"}
    owner,repo=candidates[0]
    headers={"User-Agent":"AFB-Immunefi-Scanner/0.2","Accept":"application/vnd.github+json"}
    try:
        request=Request(f"https://api.github.com/repos/{owner}/{repo}",headers=headers)
        with urlopen(request,timeout=20) as response:
            metadata=json.loads(response.read(1_000_000).decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        return {"status":"metadata_fetch_failed","repository":f"{owner}/{repo}","error":str(exc)}
    branch=metadata.get("default_branch")
    if not branch:
        return {"status":"default_branch_unknown","repository":f"{owner}/{repo}"}
    archive_url=f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
    try:
        request=Request(archive_url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.2"})
        with urlopen(request,timeout=45) as response:
            if urlparse(response.geturl()).hostname!="codeload.github.com":
                return {"status":"archive_redirect_rejected","repository":f"{owner}/{repo}"}
            archive=response.read(80_000_001)
    except (HTTPError,URLError,TimeoutError) as exc:
        return {"status":"archive_fetch_failed","repository":f"{owner}/{repo}","error":str(exc)}
    if len(archive)>80_000_000:
        return {"status":"archive_too_large","repository":f"{owner}/{repo}"}
    target=destination/f"{owner}-{repo}"
    target.mkdir(parents=True,exist_ok=True)
    written=0
    total=0
    try:
        with ZipFile(BytesIO(archive)) as bundle:
            for item in bundle.infolist():
                if item.is_dir() or not item.filename.lower().endswith(".sol"):
                    continue
                parts=item.filename.split("/")
                if len(parts)<2 or any(part in {"..",""} for part in parts):
                    continue
                relative=Path(*parts[1:])
                if relative.is_absolute() or len(relative.parts)>20:
                    continue
                if written>=2500 or total+item.file_size>50_000_000:
                    break
                data=bundle.read(item)
                if len(data)>5_000_000:
                    continue
                output=target/relative
                output.parent.mkdir(parents=True,exist_ok=True)
                output.write_bytes(data)
                written+=1
                total+=len(data)
    except BadZipFile:
        return {"status":"invalid_archive","repository":f"{owner}/{repo}"}
    return {"status":"downloaded" if written else "no_solidity_files","repository":f"{owner}/{repo}","branch":branch,"solidity_files":written,"bytes_written":total,"local_path":str(target)}
