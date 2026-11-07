# Analysis engine and logic-review model

## What the scanner analyzes

The unified `afb-immunefi analyze` command runs three complementary layers on a **local source snapshot**:

1. Built-in source heuristics for quick review leads.
2. Slither's standard detector suite, normalized from its JSON output.
3. A Slither Python-API semantic pass that maps external entrypoints, state reads/writes, modifiers, internal calls and high-level calls. It emits cross-function logic-review leads when multiple paths mutate shared state, when writer paths have asymmetric modifier coverage, or when a state-changing entrypoint needs its authorization path reviewed. This pass runs independently of the Slither CLI detector process; a missing CLI binary does not suppress it if the Python API is installed.

Aderyn is run as an additional independent analyzer when installed. Its native report is preserved.

```bash
afb-immunefi analyze \
  --source ./workspace/reconnaissance/sources/ssvlabs-ssv-network \
  --workspace ./workspace \
  --output ./workspace/findings/analysis.json
```

Outputs:
- `workspace/analysis/static/slither.json`: native Slither JSON.
- `workspace/analysis/static/aderyn.json`: native Aderyn JSON, when installed.
- `workspace/analysis/logic-review.json`: semantic contract/function/state interaction map and logic-review leads.
- The requested analysis JSON combines built-in, Slither and semantic leads.

## Logic-review rules

- `LOGIC001`: public/external state-changing entrypoint with storage writes and no Solidity modifier. This is only an authorization-path review prompt; inline checks or internal authorization may make the function safe.
- `LOGIC002`: a state variable is written by multiple functions. Review every transition against the protocol's accounting, lifecycle and cross-function invariants.
- `LOGIC003`: multiple functions write the same state variable but use asymmetric Solidity modifier sets, with at least one writer having no modifier. Review whether authorization and lifecycle preconditions are equivalent; inline/inherited checks may make the paths safe.

These rules intentionally produce `needs_review` leads, not vulnerability verdicts. The output includes functions, shared state variables, reads/writes, modifier names, internal calls and source locations so a reviewer can trace the relevant state machine. They are not a substitute for symbolic execution, fuzzing, invariant testing or protocol-specific reasoning.

## Source/build context

The intake downloader now retains Solidity files plus selected build metadata (for example Foundry/Hardhat config and package manifests) within strict archive/file limits. It does not install dependencies, initialize submodules, or execute project scripts. If imports are unresolved, prepare the project's dependencies in an isolated local environment using its documented lockfile and then rerun analysis. Do not run unknown scripts from an untrusted repository on a machine containing secrets.

## Finding states

- `potential`: built-in source heuristic matched.
- `tool_reported_unverified`: Slither detector emitted a finding.
- `needs_review`: semantic logic map found a state interaction worth tracing.
- None of these statuses means a vulnerability is confirmed.

## Validation workflow

1. Confirm exact source version and correspondence to the in-scope deployment.
2. Resolve imports, inheritance, libraries, proxy/implementation relationships and compiler settings.
3. Trace the full external entrypoint and internal/high-level call paths.
4. Define protocol invariants (for example accounting conservation, validator/cluster lifecycle consistency, nonce uniqueness or fee/reward conservation) from the protocol specification—not guessed from variable names.
5. Write deterministic unit, invariant or fuzz tests in a local isolated project/fork.
6. Reproduce the violation and establish attacker-controlled preconditions.
7. Check current scope, exclusions, known issues, audit history and impact definitions.
8. Require human review before any external report.

## Limitations

Static analysis cannot guarantee discovery of every bug or a 100% true-positive rate. Slither's parser/build can fail when compiler versions, dependencies, submodules or project configuration are missing. A zero-finding result means only that enabled checks did not emit leads; it does not prove the protocol is secure.
