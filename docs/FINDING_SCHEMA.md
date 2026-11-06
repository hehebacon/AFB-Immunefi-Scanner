# Potential finding schema

Each finding should include:

- `id`: stable local identifier
- `title` and `category`
- `asset` and `scope_status`
- `severity`: initially `undetermined`
- `confidence`: low, medium, or high
- `status`: potential, needs-review, locally-verified, rejected, or duplicate
- `source_locations`: file and line ranges
- `evidence`: concise observations tied to source material
- `preconditions`: assumptions required for the behavior
- `impact_hypothesis`: impact to validate against program definitions
- `verification`: local test references and results
- `known_issue_check`: public advisory/audit/fix comparison
- `review_notes`: human assessment

Never label an issue exploitable or eligible solely because a static detector emitted a warning.
