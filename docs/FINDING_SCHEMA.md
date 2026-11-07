# Potential finding schema

Every machine-generated result must retain evidence and an explicitly unconfirmed status.

- `id`: stable local identifier
- `rule_id`, `title`, and `category`
- `asset` and `scope_status`, when known
- `severity`: initially `undetermined`
- `confidence`: low, medium, or high
- `status`: `potential`, `tool_reported_unverified`, `needs_review`, `locally_verified`, `rejected`, or `duplicate`
- `source_locations`: file and line ranges, when available
- `evidence`: concise observations tied to source material
- `preconditions`: assumptions required for the behavior
- `impact_hypothesis`: impact to validate against program definitions
- `verification`: local test references and results
- `known_issue_check`: public advisory/audit/fix comparison
- `review_notes`: human assessment

A Slither warning, shared-state interaction, missing modifier, heuristic match or audit keyword is not proof of a vulnerability. Never label an issue exploitable or eligible solely because a static detector emitted a warning.
