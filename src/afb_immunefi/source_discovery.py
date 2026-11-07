"""Download a bounded, build-aware snapshot of a GitHub Solidity repository."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, BadZipFile
import json
import stat

MAX_ARCHIVE_BYTES=80_000_000
MAX_FILES=5000
MAX_EXTRACTED_BYTES=60_000_000
MAX_FILE_BYTES=8_000_000
SOURCE_SUFFIXES={".sol"}
BUILD_SUFFIXES={".toml",".yaml",".yml",".json",".lock",".txt",".js",".cjs",".mjs",".ts"}
BUILD_NAMES={
    "foundry.toml","remappings.txt","package.json","package-lock.json","yarn.lock",
    "pnpm-lock.yaml","hardhat.config.js","hardhat.config.cjs","hardhat.config.ts",
    "truffle-config.js","brownie-config.yaml","solhint.json",".solhint.json",
    ".gitmodules","solc-version","justfile","makefile","cargo.toml",
}
SKIP_PARTS={".git",".github","node_modules",".venv","venv","artifacts","cache","out","coverage","dist","build"}


def _keep_project_file(relative: PurePosixPath) -> bool:
    name=relative.name.lower()
    if any(part.lower() in SKIP_PARTS for part in relative.parts):
        return False
    if relative.suffix.lower() in SOURCE_SUFFIXES:
        return True
    return name in BUILD_NAMES or (relative.suffix.lower() in BUILD_SUFFIXES and name in BUILD_NAMES)


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
    headers={"User-Agent":"AFB-Immunefi-Scanner/0.4","Accept":"application/vnd.github+json"}
    try:
        request=Request(f"https://api.github.com/repos/{owner}/{repo}",headers=headers)
        with urlopen(request,timeout=20) as response:
            metadata=json.loads(response.read(1_000_000).decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        return {"status":"metadata_fetch_failed","repository":f"{owner}/{repo}","error":str(exc)[:500]}
    branch=metadata.get("default_branch")
    if not branch:
        return {"status":"default_branch_unknown","repository":f"{owner}/{repo}"}

    archive_url=f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
    try:
        request=Request(archive_url,headers={"User-Agent":"AFB-Immunefi-Scanner/0.4"})
        with urlopen(request,timeout=60) as response:
            if urlparse(response.geturl()).hostname!="codeload.github.com":
                return {"status":"archive_redirect_rejected","repository":f"{owner}/{repo}"}
            archive=response.read(MAX_ARCHIVE_BYTES+1)
    except (HTTPError,URLError,TimeoutError) as exc:
        return {"status":"archive_fetch_failed","repository":f"{owner}/{repo}","error":str(exc)[:500]}
    if len(archive)>MAX_ARCHIVE_BYTES:
        return {"status":"archive_too_large","repository":f"{owner}/{repo}"}

    target=destination/f"{owner}-{repo}"
    target.mkdir(parents=True,exist_ok=True)
    written=0
    source_count=0
    support_count=0
    total=0
    skipped=0
    try:
        with ZipFile(BytesIO(archive)) as bundle:
            for item in bundle.infolist():
                if item.is_dir() or written>=MAX_FILES or total>=MAX_EXTRACTED_BYTES:
                    continue
                raw_parts=item.filename.split("/")
                if len(raw_parts)<2 or any(part in {"..",""} for part in raw_parts):
                    skipped+=1
                    continue
                relative=PurePosixPath(*raw_parts[1:])
                if relative.is_absolute() or not _keep_project_file(relative):
                    continue
                # Never extract symlinks, encrypted entries, or oversized members.
                mode=(item.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode) or item.flag_bits & 0x1 or item.file_size>MAX_FILE_BYTES:
                    skipped+=1
                    continue
                if total+item.file_size>MAX_EXTRACTED_BYTES:
                    skipped+=1
                    continue
                data=bundle.read(item)
                if len(data)!=item.file_size:
                    skipped+=1
                    continue
                output=target/Path(*relative.parts)
                output.parent.mkdir(parents=True,exist_ok=True)
                output.write_bytes(data)
                written+=1
                total+=len(data)
                if relative.suffix.lower() in SOURCE_SUFFIXES:
                    source_count+=1
                else:
                    support_count+=1
    except BadZipFile:
        return {"status":"invalid_archive","repository":f"{owner}/{repo}"}

    if not source_count:
        status="no_solidity_files"
    elif support_count:
        status="downloaded_build_aware_snapshot"
    else:
        status="downloaded_sources_only"
    build_files=sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file() and p.name.lower() in BUILD_NAMES)
    return {
        "status":status,
        "repository":f"{owner}/{repo}",
        "branch":branch,
        "solidity_files":source_count,
        "build_support_files":support_count,
        "files_written":written,
        "bytes_written":total,
        "skipped_entries":skipped,
        "build_files":build_files,
        "local_path":str(target),
        "limitations":["This is a bounded source/build-metadata snapshot, not a full git clone.","Git submodules and package dependencies are not installed or initialized.","Build scripts are not executed by the downloader."]
    }
