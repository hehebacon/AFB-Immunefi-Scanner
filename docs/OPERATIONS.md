# Operations and local tools

## Policy-first setup
1. Initialize a workspace.
2. Fill program/policy.yaml from the selected program's official rules.
3. Confirm scope, exclusions, testing constraints, and safe-harbor terms yourself. Set review flags true only after reading current rules.
4. Place authorized Solidity source in a local directory such as ./contracts.

The scanner does not infer current Immunefi policy. Rules change; record the official source and date checked.

## Commands
```bash
afb-immunefi policy-check --workspace ./workspace
afb-immunefi inventory --source ./contracts --output ./workspace/reconnaissance/contracts.json
afb-immunefi scan --source ./contracts --output ./workspace/findings/findings.json --workspace ./workspace
afb-immunefi tools
afb-immunefi slither --source ./contracts --output ./workspace/analysis/static/slither.json --workspace ./workspace
afb-immunefi report --findings ./workspace/findings/findings.json --output ./workspace/reports/review.md
python -m unittest discover -s tests -v
```

## Tool adapters
- tools checks whether Slither, Aderyn, Foundry (forge), and solc are installed.
- slither runs Slither against a local directory only and requires the policy gate.
- Aderyn and Foundry are detected but not automatically invoked; project layouts and CLI options vary.
- Heuristic scan results are review leads, not proof of vulnerabilities.

## Safety boundary
No target-address probing, live RPC, transactions, exploit execution, wallet integration, or report submission. Fork tests require a separate manual review of program rules and an isolated local setup.
