# AFB Immunefi Scanner

A scope-first, local-first smart-contract security research assistant for authorized Immunefi research.

**Safety:** this project gathers public program information and analyzes local source code. It does not probe live targets, send transactions, execute exploits against deployed protocols, connect wallets, or submit reports.

## Implemented
- One-URL Immunefi intake: identifies the program slug from an official URL.
- Automatically fetches the program's Information page and linked Scope and Resources pages on Immunefi.
- Finds a GitHub repository linked from Resources, downloads Solidity files only, paginates public Git history (default cap 1,000 commits; hard cap 5,000), crawls linked documentation on the same host (bounded to 40 pages and depth 2), classifies references, and downloads linked audit PDFs with text extraction plus optional OCR for image-only pages.
- Saves source HTML/text, fetch timestamps, HTTP status, and SHA-256 hashes.
- Extracts scope/impact/exclusion/testing-rule evidence, chain mentions, candidate contract addresses, and related external references.
- Local Solidity inventory and conservative source-review heuristics.
- Human-confirmed policy gate, local Slither and Aderyn adapters, toolchain checks, JSON findings, Markdown reports, and unit tests.

Automated extraction is evidence collection, not a final scope decision. Every asset and impact remains unverified until checked against current program rules.

## Install
Python 3.11+:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```
Without installation, use `python run.py` instead of `afb-immunefi`.

## One-URL workflow
Paste one official Immunefi Information URL:
```bash
afb-immunefi program-url \
  --url "https://immunefi.com/bug-bounty/ssvnetwork/information/" \
  --workspace ./workspace \
  --max-commits 1000
```

The command initializes the workspace if needed, then fetches the same program's Information, Scope and Resources tabs. If Resources links a public GitHub repository, it downloads only `.sol` files (size/file-count capped), records recent public commit metadata, classifies documentation/explorer/audit references, and downloads linked PDF documents within strict size limits. PDF text is extracted when possible. Repository code is never executed.

Generated files under `workspace/program/`:
- `source-page-information.html/.txt`
- `source-page-scope.html/.txt`
- `source-page-resources.html/.txt`
- `intake.json`: fetched pages, timestamps, hashes, links
- `scope-draft.json`: candidate assets and extracted evidence
- `source-discovery.json`: linked repository and download status
- `references.json`: classified public references
- `github-history-status.json`: public commit-history collection status
- `audit-pdf-index.json`: downloaded PDF audit index, text extraction and OCR status
- `documentation-crawl-index.json`: bounded same-host documentation crawl index
- `../reconnaissance/history/`: public commit metadata
- `../reconnaissance/references/audits/`: downloaded audit PDFs and extracted text
- `../reconnaissance/contracts.json`: local Solidity inventory when source was found
- `../analysis/review-notes/source-leads.json`: potential source-review leads, with scope still marked unverified
- `scope-report.md`: human-readable scope-style report

If a tab is unavailable, its file will not be created. Check the returned output list.

## Local source analysis
After reviewing the scope report and completing `workspace/program/policy.yaml` from the official rules:
```bash
afb-immunefi policy-check --workspace ./workspace
afb-immunefi tools
afb-immunefi inventory --source ./contracts --output ./workspace/reconnaissance/contracts.json
afb-immunefi analyze --source ./contracts --output ./workspace/findings/analysis.json --workspace ./workspace
afb-immunefi slither --source ./contracts --output ./workspace/analysis/static/slither.json --workspace ./workspace
afb-immunefi report --findings ./workspace/findings/analysis.json --output ./workspace/reports/review.md
python -m unittest discover -s tests -v
```


## Deployed-source verification (read-only)
Create `workspace/deployment-targets.json` with chain IDs and exact contract addresses copied from the official Scope page:

```json
{
  "targets": [
    {"label": "Vault", "chain_id": "1", "address": "0x0000000000000000000000000000000000000000"}
  ]
}
```
Replace the example address before running:

```bash
afb-immunefi verify-deployments --targets ./workspace/deployment-targets.json --output ./workspace/verification/deployed-source.json --workspace ./workspace
```
This queries Sourcify public verification metadata only. It does not call contract methods, send transactions, or prove Immunefi scope. An unavailable Sourcify record is **unknown**, not evidence of an unverified or malicious contract.

## Important limitations
- Program page parsing can miss content rendered only by JavaScript.
- Candidate addresses are not automatically treated as in-scope assets.
- Documentation crawling is intentionally bounded (40 pages, depth 2, same host, 2 MB/page); JavaScript-rendered content, linked external hosts and deeper pages may be missed.
- Git history is paginated beyond the former 100-commit ceiling (default 1,000, hard cap 5,000); this is still not an unlimited forensic archive.
- OCR is optional and requires `tesseract-ocr` plus `poppler-utils`; No extra Python package is required; install the system binaries with `sudo apt install tesseract-ocr poppler-utils`. OCR quality depends on scan quality/language packs and is capped at 120 pages per PDF.
- GitHub source downloads remain limited to Solidity files and do not establish deployed-source correspondence by themselves. Use the optional Sourcify verification workflow for address/chain-specific metadata checks; only an exact match is strong source-match evidence, and it does not establish Immunefi scope.
- No RPC, contract probing, live testing, exploit execution, wallet integration, or automatic submission.
- Slither and heuristic outputs are leads requiring independent validation, not confirmed vulnerabilities.

See `docs/ANALYSIS_ENGINE.md`, `docs/OPERATIONS.md`, `docs/ARCHITECTURE.md`, and `docs/REVIEW_CHECKLIST.md`.
