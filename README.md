# AFB Immunefi Scanner

A local-first smart-contract analysis tool for authorized bug-bounty research. It is designed to **analyze code and identify reviewable bug candidates**, not to stop at public-information collection.

**Safety boundary:** the tool collects public program/source material and analyzes local files. It does not probe live targets, send transactions, execute exploits against deployed protocols, connect wallets, or submit reports.

## Analysis capabilities

- One-URL Immunefi intake for Information, Scope and Resources.
- Bounded GitHub source snapshot that includes Solidity and selected build metadata (Foundry/Hardhat configs and package manifests); it does not install dependencies or execute repository scripts.
- Local Solidity inventory and conservative source-text review leads.
- Slither standard detector suite with normalized JSON findings.
- Slither Python-API semantic logic review: external entrypoints, modifiers, state reads/writes, internal/high-level calls, shared-state writers and cross-function state interaction maps. This pass runs independently from the Slither CLI detector process when the Python API is available.
- Optional Aderyn analysis with its native report preserved.
- Human-confirmed scope/policy gate, JSON findings and Markdown review reports.
- Unit tests for parsing, normalization and logic-review output.

Semantic logic findings are **review leads**, not confirmed vulnerabilities. Real business-logic verification still requires protocol-specific invariants and deterministic local tests.

## Install

Python 3.11+:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install Slither in the same Python environment as AFB (for example, using the official Slither installation instructions). Install the repository's required Solidity compiler version and dependencies only in an isolated development environment. Aderyn is optional.

## One-URL intake

```bash
afb-immunefi program-url \
  --url "https://immunefi.com/bug-bounty/ssvnetwork/information/" \
  --workspace ./workspace \
  --max-commits 1000
```

The command retrieves the official program tabs and discovers the source repository linked from Resources. It downloads a bounded snapshot of Solidity files and selected build metadata, public commit metadata, linked audit PDFs and bounded documentation pages. It does not run analysis before the policy gate is confirmed.

## Run the actual analyzers

First review `workspace/program/scope-report.md`, verify the current official scope and testing rules, and complete `workspace/program/policy.yaml`. Then run:

```bash
afb-immunefi policy-check --workspace ./workspace
afb-immunefi tools
afb-immunefi analyze \
  --source ./workspace/reconnaissance/sources/ssvlabs-ssv-network \
  --output ./workspace/findings/ssv-analysis.json \
  --workspace ./workspace
```

The unified analysis produces:
- `workspace/analysis/static/slither.json`: Slither detector output.
- `workspace/analysis/static/aderyn.json`: Aderyn output, if installed.
- `workspace/analysis/logic-review.json`: semantic entrypoint/state-interaction map and logic-review leads.
- `workspace/findings/ssv-analysis.json`: combined heuristic, Slither and logic-review findings.

To run Echidna property fuzzing against a project-specific local harness:
```bash
afb-immunefi echidna \
  --source ./workspace/reconnaissance/sources/ssvlabs-ssv-network \
  --contract SSVAccountingEchidna \
  --output ./workspace/analysis/static/echidna.json \
  --workspace ./workspace \
  --test-limit 5000 \
  --seq-len 50
```

The command requires Echidna and a harness exposing meaningful `echidna_*` properties. It runs only against the local source project and stores the JSON campaign output. A falsified property is a local counterexample for review, not an automatic vulnerability verdict.

To run Slither alone:
```bash
afb-immunefi slither \
  --source ./workspace/reconnaissance/sources/ssvlabs-ssv-network \
  --output ./workspace/analysis/static/slither.json \
  --workspace ./workspace
```

To explore bounded CFG path conditions (Z3 is installed with the analysis extra), derive structural invariant hypotheses, and inspect path feasibility counts, run the unified `analyze` command above. Unsupported branch expressions remain unknown; this is not full EVM symbolic execution.

Map local Foundry regression tests to review leads with a JSON file:
```json
{
  "finding_tests": {
    "LOGIC-0001": "test_AFB_LOGIC_0001",
    "SLITHER-0001-01": "test_AFB_SLITHER_0001"
  }
}
```
Then execute only against a local Foundry project:
```bash
afb-immunefi validate \
  --source ./workspace/reconnaissance/sources/ssvlabs-ssv-network \
  --test-map ./workspace/analysis/finding-tests.json \
  --output ./workspace/analysis/validation.json \
  --workspace ./workspace
```
A failing mapped test is a reproduction candidate requiring trace/root-cause review; it is not automatically a confirmed vulnerability.

Compare test outcomes across two local snapshots:
```bash
afb-immunefi differential \
  --reference ./workspace/snapshots/baseline \
  --candidate ./workspace/snapshots/candidate \
  --output ./workspace/analysis/differential.json \
  --workspace ./workspace
```
This compares Foundry test outcomes, not complete EVM state equivalence.

Measure TP/FP/FN/TN only against a labeled fixture manifest:
```json
{
  "name": "my-reviewed-fixtures",
  "positive_cases": ["BUG-A", "BUG-B"],
  "negative_cases": ["FALSE-POSITIVE-A", "CLEAN-FIXTURE"]
}
```
```bash
afb-immunefi benchmark \
  --findings ./workspace/findings/ssv-analysis.json \
  --manifest ./workspace/benchmarks/manifest.json \
  --output ./workspace/benchmarks/metrics.json
```
The metrics describe that corpus only; do not treat them as real-world accuracy estimates.

To run tests:
```bash
python -m unittest discover -s tests -v
```

## Logic analysis: what it looks for

- State-changing public/external entrypoints and their Solidity modifiers.
- State variables read and written by each function.
- Shared state variables with multiple writer paths, which can hide inconsistent accounting or lifecycle transitions.
- Cross-function relationships to help build state-machine and invariant tests.

Current logic rules are conservative review prompts. Inline authorization, inherited checks, internal call paths and protocol-specific invariants require deeper validation. A finding is never marked confirmed automatically.

## SSV Network-specific review constraints

For SSV Network, follow the current Immunefi Scope and program rules. The program requires a functional PoC and states that testing must use local forks rather than mainnet or public-testnet deployed code. Previously disclosed audit findings and known issues must be checked before treating a candidate as novel. The scanner does not automate PoC execution against live infrastructure.

## Deployed-source verification (read-only)

After scope review, create `workspace/deployment-targets.json` using exact chain IDs and full addresses copied from the official Scope page. Then use:
```bash
afb-immunefi verify-deployments \
  --targets ./workspace/deployment-targets.json \
  --output ./workspace/verification/deployed-source.json \
  --workspace ./workspace \
  --source ./workspace/reconnaissance/sources/ssvlabs-ssv-network
```

Sourcify metadata and local source comparison are correspondence evidence only; they do not prove scope or exploitability.

## Important limitations

- JavaScript-rendered program content may be missed.
- Source snapshot limits can omit large files, build files outside the allowlist, submodules, dependencies and generated sources.
- Slither may fail if the compiler version or dependencies are missing; the tool must report this rather than treating it as a clean scan.
- Aderyn is optional and may produce a different set of findings.
- Static analysis cannot prove absence of vulnerabilities. Zero findings is not a security guarantee.
- All machine-generated findings require manual triage, local reproduction, scope/known-issue checks and human review.

See `docs/ANALYSIS_ENGINE.md`, `docs/OPERATIONS.md`, `docs/ARCHITECTURE.md`, and `docs/REVIEW_CHECKLIST.md`.


## Automatic local scope mode

Update the local clone and reinstall the analysis extras:

```bash
bash update.sh
```

Create a scope folder with this layout:

```text
scopes/
  my-authorized-scope/
    source/                 # Drop the local Solidity source tree here
    workspace/
      program/
        policy.yaml         # Created automatically on first watch
```

Start the watcher:

```bash
bash watch-scopes.sh
```

The watcher notices new or changed Solidity source and runs the unified local analysis automatically after the scope policy has been reviewed and explicitly confirmed. It never bypasses the policy gate. It writes the report to `scopes/<name>/workspace/findings/analysis.json`. Keep the watcher running in a terminal or configure it as a user-level service.

The semantic pass now includes five concurrent review perspectives: authorization paths, shared-state writers, external interactions, transition-guard asymmetry, and coupled accounting updates. They operate on Slither's parsed local-source facts and emit unverified hypotheses. They are not five independent AI models and do not guarantee zero-day discovery.

The exact message `<no bugs more appear on this scope>` is printed only when the unified report contains zero findings. It means no enabled analyzer emitted a finding in that run; it is not a security proof and does not imply that all possible bugs have been found.
