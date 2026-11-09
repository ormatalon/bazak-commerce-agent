# Comprehensive V2 code review — 9 November 2026

Scope: application schemas, parser/state, currency, retrieval and fallback, the approved product-type node, response generation, Chainlit callbacks and persistence, observability, index/catalog caches, evaluation/scoring/upload/calibration code, existing tests and the card component.

The review fixes implementation defects and consolidates duplicated logic. It does not change the approved retrieval policy, add model calls or dependencies, retune thresholds, or certify draft relevance labels. All source changes and regression cases were prepared before running tests, as requested.

## High-priority defects fixed

- **Currency refinement could silently reinterpret a retained bound.** Changing a maximum from ILS to USD left an untouched minimum in the old numeric units under the new currency. The parser merge now rejects this ambiguous edit and the pipeline asks for the complete range in the new currency. Original state is preserved.
- **Optional tracing could break chat.** Client construction, trace updates, header extraction and shutdown were not all isolated. Model client creation now survives instrumentation failures; a small safe span adapter protects trace operations without retrying application work or hiding its original exception.
- **SQL exceptions could expose parameter values.** The framework's SQL exception formatter included statement parameters. Persistence now executes the same parameterized transactions with exception-type-only logging and retains recovery behavior.
- **Concurrent and stale UI actions could affect the wrong state/chat.** Busy messages were dropped, and stale show-more actions could page a newer search. A per-session lock queues input; action identity and thread identity are checked before acting. Model replies are discarded if the user has switched conversations.

## Other correctness fixes

- Numeric-only follow-ups retain their actual text; response language is passed separately.
- An explicit count overrides prior show-all state, clearing a sort removes its old direction, and obsolete currency display terms are removed when currencies change.
- Runtime/index/model errors are no longer caught as shopper ambiguity. Only request preparation errors take the clarification path.
- Non-finite numeric facts/constraints and malformed query/configuration values are rejected. Non-shopping intents discard stray searches before nested validation.
- Catalog/category data is loaded together; catalog IDs and category membership are checked. Cache writes are atomic; corrupt embedding metadata is rebuilt, and optional cache-write failures leave the index usable.
- Corrupt-card metadata is skipped during resume. Structured history stays at the six messages used by the parser rather than being copied in full into every saved reply.
- Earlier database corruption backups are retained, and failed file recovery does not announce that recovery succeeded.
- Product-type verdict parsing rejects coerced boolean strings; unchecked results still fail closed.

## Evaluation fixes and simplification

- Live replay and free re-scoring use `score_record`; invariant aggregation and expectation overlays have one implementation.
- Execution failures contribute zero to applicable accuracy metrics. Partial predictions survive scorer errors and can be re-scored without calling a model again.
- Empty results for an unrelated search no longer earn perfect legacy retrieval credit. Top-k ties are scored as equivalent answers. Unknown labels cannot be treated as exhaustive judgments.
- Dollar-amount checks no longer whitelist ratings, and alternative disclosure requires the actual disclosure line and its stated values rather than a title mention alone.
- Evidence is checked for completeness, duplicate identities, manifest membership and non-finite metrics before upload. Conversation turns must be lists, preventing accidental character-by-character replay.
- Calibration refuses stale catalog labels and configurations that accept no positive examples. Dataset hashes are computed once per source file; dynamic imports and redundant tracing state/buffers were removed.

## Validation

All implementation changes and regression cases were written before the final validation batch.

- Offline pytest suite: **68 passed**. This includes actual SQLite transaction/error handling, UI message queueing and chat-switch guards, currency/state regressions, cache failure handling, trace-failure isolation, strict verdict validation and independent scoring/evidence checks.
- Python syntax compilation and Git whitespace checks passed.
- All **167 saved evaluation cases** re-scored successfully, with zero recorded execution errors. Numeric/sort/count extraction remains 72/72 on those predictions; forbidden-product checks remain 10/10. Exact-path numeric compliance is 132/132 applicable cases under the corrected denominator, and mechanical disclosure checks are 167/167.
- The re-scored artifacts are in `evals/artifacts/review-rescored/`; original artifacts remain unchanged. No paid model calls or new remote experiment uploads were made for this review.

Re-scoring validates the corrected scoring path on historical predictions. It does not measure the revised parser prompt or claim that the previous semantic-quality gaps have been resolved.

## Remaining limits

The previous evaluation's relevance/recall failures, unreviewed semantic labels and missing prospective holdout remain open. This review does not claim to fix semantic quality by changing gold labels or thresholds. Historical live scores describe their recorded prediction revision; free re-scoring is separate evidence and does not test the new parser prompt against a live model.
