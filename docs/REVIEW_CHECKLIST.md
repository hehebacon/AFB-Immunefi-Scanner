# Manual smart-contract review checklist

Use this as a prompt for human review, not as an automated verdict.

## Scope and rules
- [ ] Exact program and current official policy URL recorded
- [ ] Asset/address/repository is explicitly in scope
- [ ] Exclusions and known issues checked
- [ ] Testing limits and safe-harbor terms reviewed
- [ ] Impact category matches the program's current definitions

## Source and architecture
- [ ] Correct deployed source and compiler version established
- [ ] Proxy, implementation, beacon, facets, and upgrade authority mapped
- [ ] Inheritance, libraries, and external dependencies identified
- [ ] Privileged roles and role-transfer paths mapped
- [ ] Critical state variables and invariants documented
- [ ] External calls, callbacks, token hooks, and oracle dependencies reviewed

## Logic review
- [ ] Authorization and initialization paths
- [ ] Reentrancy and cross-function state consistency
- [ ] Accounting, shares, rounding, and precision
- [ ] Oracle freshness, decimals, liquidity, and manipulation assumptions
- [ ] Signature domain, nonce, expiry, and replay protection
- [ ] ERC20 return values, fee-on-transfer, rebasing, and non-standard tokens
- [ ] Upgrade and storage-layout safety
- [ ] Bridge message validation and replay protection, if applicable
- [ ] State-machine transitions and emergency/pause behavior

## Verification and reporting
- [ ] Reproducible local test with explicit preconditions
- [ ] Expected versus actual behavior recorded
- [ ] Impact demonstrated without touching live funds
- [ ] False-positive and known-issue checks completed
- [ ] Severity justified against program definitions
- [ ] Report includes exact source locations and concise evidence
- [ ] Human review completed before any external submission
