# Review checklist (solo build, spec Annexure I)

Every pull request is reviewed against this list before merge.

- [ ] CI green (python, web, security).
- [ ] No number reaches a user unless it comes from a tool result with `source` and `fetched_at`.
- [ ] No safety sentence outside `config/phrases/<code>.yaml`; Simple mode shows no codes (PFZ, IMBL, H1–H8).
- [ ] No personal data (phone, name, email, coordinates) in Redis, Neo4j, logs, traces or cache keys.
- [ ] No secret in code, Bicep, images or `EXPO_PUBLIC_*`; `.env` files untracked.
- [ ] Governed files changed (`constraints.yaml`, `boats.yaml`, `qc.yaml`, phrases, aliases, prompts, model)?
      → config/prompt version bumped, `safety-hold` label applied, 24 hours passed since the last commit.
- [ ] New behaviour has tests; any fixed wrong answer has a row in `tests/failures/failures.yaml`.
- [ ] Assumptions left as `TODO(tarangyukti):` and listed in the PR description.
