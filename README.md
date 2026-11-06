# AFB Immunefi Scanner

A scope-first, local-first smart-contract security research assistant for **authorized Immunefi bug bounty work**.

> The scanner is an analysis assistant, not an autonomous exploitation tool. It does not send transactions to live targets, manipulate live protocols, or submit reports automatically.

## Current status

**Bootstrap / Milestone 1.** The repository currently provides a Python CLI foundation and a structured workspace layout. Integrations and analysis engines are added incrementally.

## Design principles

- **Policy before code:** record program scope, exclusions, impact requirements, and testing restrictions before analysis.
- **Evidence-first:** every potential finding must link to source locations and supporting evidence.
- **Local verification only:** tests and PoCs run against local fixtures or explicitly permitted isolated forks.
- **Human approval:** severity, exploitability, report quality, and submission remain human-reviewed.
- **No live exploitation:** no fund-moving transactions, live oracle manipulation, unauthorized probing, or automatic submissions.

## Pipeline

1. **Program discovery & policy intake** — program URL, assets, in-scope components, exclusions, safe-harbor conditions, impact definitions.
2. **Contract reconnaissance** — addresses, chain, verified source, proxy/implementation relationships, compiler and dependencies.
3. **Documentation intelligence** — official docs, architecture, audits, changelogs, and public fixes.
4. **Static analysis** — Slither, Aderyn, compiler checks, dependency inventory.
5. **Review engines** — access control, state transitions, accounting, reentrancy, signatures, oracle assumptions, token compatibility, upgradeability, and integration boundaries.
6. **Local verification** — unit tests, invariants, regression tests, and isolated PoCs.
7. **Triage & reporting** — evidence, scope check, impact reasoning, confidence, duplicate/known-issue review, human approval.

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
afb-immunefi --help
afb-immunefi init --workspace ./workspace
afb-immunefi status --workspace ./workspace
```

Or run without installing:

```bash
python run.py --help
python run.py init --workspace ./workspace
```

## Workspace

```text
workspace/
  program/
    policy.yaml
    scope.yaml
  reconnaissance/
    contracts.json
    sources/
    docs/
  analysis/
    static/
    review-notes/
  findings/
    findings.json
  verification/
    local-tests/
  reports/
```

## Tool integrations (planned)

- Slither and Aderyn for local source analysis
- Foundry for local unit, invariant, and regression tests
- SQLite for indexed program and finding metadata
- Official program pages and public documentation as source material

The tool will not treat automated detector output as a confirmed vulnerability. Every result starts as a **potential finding** until manually validated.

## Development roadmap

- [x] Repository bootstrap and CLI skeleton
- [ ] Program policy and scope schema
- [ ] Contract/source inventory
- [ ] Documentation and public-history collection
- [ ] Slither/Aderyn adapters
- [ ] Review-engine framework
- [ ] Local Foundry verification workflow
- [ ] Finding triage and report generator
- [ ] Dashboard

## Responsible use

Only analyze programs and assets where you have authorization. Read and follow each Immunefi program's current rules, scope, exclusions, and safe-harbor terms. Do not test live systems in ways prohibited by the program. Keep proof-of-concept work in local test environments unless the program explicitly permits a particular test.

## License

MIT
