# Architecture

## Processing stages

`discovery -> policy -> reconnaissance -> intelligence -> source_analysis -> review_engines -> verification -> triage -> reporting`

Each stage writes artifacts into a workspace. Stages should be reproducible and preserve source provenance.

## Core records

### Program policy
Stores program identity, scope, excluded classes, required impacts, testing constraints, safe-harbor review, and last-checked timestamp.

### Asset
Stores chain, address or repository path, asset type, source verification state, proxy metadata, and scope status.

### Potential finding
Stores category, title, severity estimate, confidence, affected asset, source location, evidence, preconditions, impact hypothesis, verification status, and known-issue comparison.

Severity and validity must not be inferred from a detector label alone.

## Safety gates

- No analysis run against a target until its program policy and scope have been reviewed.
- No live transactions or automated state-changing calls.
- PoCs use local fixtures or isolated local environments.
- Fork-based tests require explicit confirmation that the program permits the intended testing method.
- No automatic report submission.
