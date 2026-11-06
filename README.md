# AFB Immunefi Scanner

A scope-first, local-first smart-contract security research assistant for authorized Immunefi research.

**Safety:** this project gathers public program information and analyzes local source code. It does not probe live targets, send transactions, execute exploits against deployed protocols, connect wallets, or submit reports.

## Implemented
- One-URL Immunefi intake: identifies the program slug from an official URL.
- Automatically fetches the program's Information page and linked Scope and Resources pages on Immunefi.
- Finds a GitHub repository linked from the Resources page, downloads only Solidity files from its public archive, then runs local inventory and heuristic review.
- Saves source HTML/text, fetch timestamps, HTTP status, and SHA-256 hashes.
- Extracts scope/impact/exclusion/testing-rule evidence, chain mentions, candidate contract addresses, and related external references.
- Local Solidity inventory and conservative source-review heuristics.
- Human-confirmed policy gate, local Slither adapter, toolchain checks, JSON findings, Markdown reports, and unit tests.

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
  --workspace ./workspace
```

The command follows only the same program's Immunefi Scope and Resources tabs. If Resources links a public GitHub repository, it downloads only `.sol` files (size/file-count capped) without executing repository code, then runs local source inventory and conservative review heuristics. Other external links are recorded as references, not crawled.

Generated files under `workspace/program/`:
- `source-page-information.html/.txt`
- `source-page-scope.html/.txt`
- `source-page-resources.html/.txt`
- `intake.json`: fetched pages, timestamps, hashes, links
- `scope-draft.json`: candidate assets and extracted evidence
- `source-discovery.json`: linked repository and download status
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
afb-immunefi report --findings ./workspace/findings/findings.json --output ./workspace/reports/review.md
python -m unittest discover -s tests -v
```

## Important limitations
- Program page parsing can miss content rendered only by JavaScript.
- Candidate addresses are not automatically treated as in-scope assets.
- Non-GitHub documentation and arbitrary third-party pages are recorded but not automatically crawled.
- GitHub source downloads are limited to Solidity files and do not establish that those files correspond to every in-scope deployed asset.
- No RPC, contract probing, live testing, exploit execution, wallet integration, or automatic submission.
- Slither and heuristic outputs are leads requiring independent validation, not confirmed vulnerabilities.

See `docs/ANALYSIS_ENGINE.md`, `docs/OPERATIONS.md`, `docs/ARCHITECTURE.md`, and `docs/REVIEW_CHECKLIST.md`.
