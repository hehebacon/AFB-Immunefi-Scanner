# AFB Immunefi Scanner

A scope-first, local-first smart-contract security research assistant for authorized Immunefi research.

**Safety:** this project performs local source inventory and conservative source review. It does not probe live targets, send transactions, execute exploits against deployed protocols, connect wallets, or submit reports.

## Implemented
- One-URL Immunefi program intake: fetches the official information page, identifies the program slug, saves source HTML/text and builds an evidence-based scope draft/report.\n- Workspace initialization and readiness status.
- Human-confirmed policy gate (scope, exclusions, testing restrictions, safe harbor, last-checked date).
- Local Solidity inventory: SHA-256, compiler pragma, contracts/interfaces/libraries, imports.
- Conservative source heuristics for call ordering, public/external functions, unchecked blocks, delegatecall, tx.origin, timestamps, selfdestruct, ecrecover, and low-level calls.
- Local Slither adapter, toolchain availability checks for Slither/Aderyn/Foundry/solc.
- JSON findings and Markdown review report generation.
- Unit tests for core inventory, heuristic, and policy behavior.

All heuristic results are low-confidence potential leads. They are not confirmed vulnerabilities and do not assign severity.

## Install
Python 3.11+:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```
Without installation, use `python run.py` instead of `afb-immunefi`.

## Quick start
```bash
afb-immunefi init --workspace ./workspace
# Edit workspace/program/policy.yaml using official current program rules.
afb-immunefi policy-check --workspace ./workspace
afb-immunefi tools
afb-immunefi inventory --source ./contracts --output ./workspace/reconnaissance/contracts.json
afb-immunefi scan --source ./contracts --output ./workspace/findings/findings.json --workspace ./workspace
afb-immunefi slither --source ./contracts --output ./workspace/analysis/static/slither.json --workspace ./workspace
afb-immunefi report --findings ./workspace/findings/findings.json --output ./workspace/reports/review.md --program "Program name"
python -m unittest discover -s tests -v
```

## Policy gate
Before `scan` or `slither`, complete `program/policy.yaml` from the selected program's official rules. Set `scope_confirmed`, `testing_constraints_reviewed`, and `safe_harbor_reviewed` to true only after personally reviewing those conditions. Record `last_checked` and at least one in-scope asset. The scanner does not scrape or infer current program policy.

## Tools
- `tools` checks local installation of Slither, Aderyn, Foundry (`forge`), and solc.
- `slither` runs Slither only against a local directory and writes JSON output.
- Aderyn and Foundry are detected but not automatically invoked because CLI options and project layouts can vary. Run them locally according to their official docs.
- Heuristics can produce false positives and false negatives. Manually inspect source context, tests, invariants, and protocol assumptions.

## Not implemented
No automatic Immunefi program scraping, remote contract fetching, RPC/fork orchestration, autonomous exploit generation, live testing, wallet integration, or automatic submission. Those require separate program-specific authorization and human review.

See docs/OPERATIONS.md and docs/ARCHITECTURE.md.
