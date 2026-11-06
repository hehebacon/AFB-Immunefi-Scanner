# Analysis engine and validation model

## What the tool can establish

The scanner operates on a local source directory. It records source inventory and deterministic source-review leads. If Slither is installed, it also normalizes Slither's JSON detector output into the common finding format.

The unified command is:

\`\`\`bash
afb-immunefi analyze \
  --source ./workspace/reconnaissance/sources/<owner>-<repo> \
  --workspace ./workspace \
  --output ./workspace/findings/analysis.json
\`\`\`

Use \`--no-slither\` to explicitly run only the built-in local checks.

## Finding states

- \`potential\`: a built-in heuristic matched source text; this is a review lead.
- \`tool_reported_unverified\`: Slither reported a detector result; inspect the complete detector description and source mapping.
- A confirmed vulnerability is never assigned automatically.

A detector can identify a suspicious pattern without proving that an attacker can reach it, satisfy its preconditions, or cause an in-scope impact. Static analysis can also miss business-logic and cross-contract issues.

## Required validation before calling something a bug

1. Confirm the source corresponds to the deployed asset and exact version.
2. Resolve imports, inheritance, libraries, proxy/implementation relationships, compiler version, and relevant configuration.
3. Read the full function and call path, not just the matched line.
4. Establish attacker-controlled inputs and reachable preconditions.
5. Reproduce the behavior with a deterministic local unit or invariant test in an isolated project.
6. Compare expected and actual state changes and identify the root cause.
7. Check the current Immunefi scope, exclusions, known issues, testing restrictions, and impact definitions.
8. Have a human reviewer inspect the evidence before any report is submitted.

## Tool coverage and failure handling

The JSON output records:
- number of Solidity files inventoried;
- number of heuristic leads;
- number of normalized Slither detector elements;
- whether Slither was completed, missing, or failed;
- a fixed validation policy that keeps all machine-generated results unverified.

A missing tool is reported as missing, not silently treated as a clean scan. A Slither non-zero exit code is not automatically a scan failure: inspect its JSON output and stderr because detector findings can affect exit status.

## What cannot be guaranteed

No static analyzer can guarantee detection of every vulnerability or a 100% true-positive rate. Results depend on source completeness, build configuration, compiler support, dependencies, analysis rules, and the correctness of the threat model. A zero-finding result means only that the enabled checks did not report a lead; it does not prove the contract is secure.
