# AFB Immunefi Scanner

A scope-first, local-first smart-contract security research assistant for authorized Immunefi research.

**Safety:** this project gathers public program information and analyzes local source code. It does not probe live targets, send transactions, execute exploits against deployed protocols, connect wallets, or submit reports.

## Implemented
- One-URL Immunefi intake: identifies the program slug from an official URL.
- Automatically fetches the program's Information page and linked Scope and Resources pages on Immunefi.
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

The command follows only the same program's Immunefi Scope and Resources tabs. It records third-party links found there as references, but does not automatically crawl arbitrary external sites or clone repositories.

Generated files under `workspace/program/`:
- `source-page-information.html/.txt`
- `source-page-scope.html/.txt`
- `source-page-resources.html/.txt`
- `intake.json`: fetched pages, timestamps, hashes, links
- `scope-draft.json`: candidate assets and extracted evidence
- `scope-report.md`: human-readable scope-style report

If a tab is unavailable, its file will not be created. Check the returned output list.

## Local source analysis
After reviewing the scope report and completing `workspace/program/policy.yaml` from the official rules:
```bash
afb-immunefi policy-check --workspace ./workspace
afb-immunefi tools
afb-immunefi inventory --source ./contracts --output ./workspace/reconnaissance/contracts.json
afb-immunefi scan --source ./contracts --output ./workspace/findings/findings.json --workspace ./workspace
afb-immunefi slither --source ./contracts --output ./workspace/analysis/static/slither.json --workspace ./workspace
afb-immunefi report --findings ./workspace/findings/findings.json --output ./workspace/reports/review.md
python -m unittest discover -s tests -v
```

## Important limitations
- Program page parsing can miss content rendered only by JavaScript.
- Candidate addresses are not automatically treated as in-scope assets.
- External documentation, repositories, and explorer links are recorded but not yet fetched/analyzed automatically.
- No RPC, contract probing, live testing, exploit execution, wallet integration, or automatic submission.
- Heuristic results are potential review leads, not confirmed vulnerabilities.

See `docs/OPERATIONS.md`, `docs/ARCHITECTURE.md`, and `docs/REVIEW_CHECKLIST.md`.
