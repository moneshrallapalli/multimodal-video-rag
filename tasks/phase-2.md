# Phase 2 — Ingestion Pipeline — TODO

Turn the Phase 1 mocked admin ingestion flow into a real async pipeline while preserving the
existing public search, admin UI, and typed response contracts.

Conventions: granular conventional commits, push frequently, no `Co-Authored-By` trailer.

## Tasks

- [ ] A. Shared ingestion contracts and helpers
- [ ] B. Admin API writes jobs to DynamoDB and enqueues SQS messages
- [ ] C. Worker consumes SQS jobs and updates DynamoDB status
- [ ] D. YouTube metadata/audio download and deterministic S3 artifact layout
- [ ] E. Frame extraction artifacts
- [ ] F. Transcript artifact path
- [ ] G. Duplicate-job/idempotency behavior
- [ ] H. Tests, docs, and local/AWS smoke-test notes

## Guardrails

- Preserve Phase 1 frontend routes, component structure, and API response shapes.
- Keep public search mocked until Phase 3/4 replaces retrieval and generation.
- Do not change or redeploy Phase 0 infrastructure unless a Phase 2 gap requires a scoped additive
  change.
- Do not print or commit secrets.

