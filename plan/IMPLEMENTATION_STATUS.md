# V2 implementation status

## Branches and scope

Each implementation phase has its own branch, with a merge commit into `v2` after implementation checks:

1. `v2-phase-1-foundation`: schemas, pinned configuration, source dataset loader, draft labels and split manifest, minimal tracing.
2. `v2-phase-2-index`: pinned local E5 adapter, dual-vector index, atomic validated cache.
3. `v2-phase-3-retrieval`: structured parser, strict currency bounds, soft categories, full-inventory sorting and pagination.
4. `v2-phase-4-conversation`: disclosed fallback, grounded responder, Chainlit cards, SQLite persistence and resume.
5. `v2-phase-5-evaluation`: independent metrics, source-case replay, guarded calibration, relevance feasibility probes.
6. `v2-phase-6-langsmith`: stage/LLM/persistence tracing, immutable recorded-output experiments, monitoring journal/view and runbook.

Implementation is distinct from release acceptance. Final relevance feasibility, full-suite live scoring, reviewed semantic labels, baseline comparison and prospective holdout evidence are still required. No final semantic quality claim is made.

## Verification completed before full evaluation

- 22 offline checks pass. They cover shared contracts, index/cache identity, weighted scores, currency arithmetic, refinements, strong wrong-category matches, zero variance, fallback disclosures, preserved budgets, exclusions, show-more inventory, persistence recovery, metric math and trace redaction/failure isolation.
- Application import/startup succeeded with the actual 194-product cache, downloaded pinned model, offline model loading, index, login and SQLite setup.
- Two live source cases (`deterministic:1` and `deterministic:2`) completed without execution errors. This is a smoke check, not the 167-case evaluation or a release result. One case exercised budget fallback.
- LangSmith workspace access and experiment upload were verified. The smoke experiment contains exactly the recorded local outputs; upload made no additional shopping-model calls.
- Local smoke evidence: `evals/artifacts/final-smoke/`. Monitoring view: `monitoring/dashboard.html`. These contain generated local artifacts and are intentionally ignored by Git.
- Smoke experiment: [recorded two-case evaluation](https://smith.langchain.com/o/7b56a565-d567-4ebc-a294-baf18f745709/datasets/1f57f68c-a329-4916-bf75-eed072af37d9/compare?selectedSessions=95a94702-021e-4d0c-9b6f-8fedfc26da1c).

## Known limitations pending final evaluation

- Relative relevance thresholds are provisional. The revised plan explicitly requires checking unsupported product types and stopping before introducing an unapproved gate.
- All new semantic annotations and expectation changes are drafts. No independent reviewer-authored prospective holdout exists yet; calibration refuses draft-only data.
- The two-case smoke check already shows a parser numeric/sort/count mismatch and one extra legacy category result. These are retained in the local report rather than presented as passes.
- Runtime token detail is in LangSmith provider spans. Cost is unknown unless pricing is configured. No automated judge, alerting or automatic dataset synchronization was added.
- Pre-existing deletions of `Design Decisions.md` and `plan/PLAN.md`, and untracked Chainlit translations, were not included in implementation commits.
